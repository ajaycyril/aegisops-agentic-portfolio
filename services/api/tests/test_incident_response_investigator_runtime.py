import json
from pathlib import Path
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from aegisops_api.db.models import AuditEvent, EvidenceRecord, WorkflowRun
from aegisops_api.main import (
    app,
    get_database_session,
    get_tool_adapter_registry,
    get_tool_policy_evaluator,
)
from aegisops_api.policy import PolicyDecision
from aegisops_api.tools import (
    ToolCallAuthorizationRequest,
    ToolCallAuthorizationResponse,
    ToolCallExecutionRequest,
    ToolCallExecutionResponse,
    ToolPolicyEvaluator,
)
from aegisops_api.tools.adapters import ToolAdapterRegistry
from aegisops_api.tools.execution import ToolPolicyDecisionSummary
from aegisops_api.tools.registry import ToolRegistry
from aegisops_api.workflows.incident_response_investigator import (
    IncidentInvestigationRejectedError,
    IncidentInvestigationRequest,
    ReplayFixtureError,
    collect_incident_evidence,
)
from aegisops_api.workflows.registry import WorkflowRegistry


class FakeToolPolicyEvaluator:
    async def evaluate(self, _input_payload: dict[str, Any]) -> PolicyDecision:
        return PolicyDecision(
            package_path="aegisops.tool_access",
            allowed=True,
            requires_approval=False,
            decision_id="decision-runtime",
            reason_codes=[],
            result={"allow": True},
        )


class FakeIncidentToolRuntime:
    def __init__(self) -> None:
        self.tool_by_call_id: dict[UUID, str] = {}
        self.run_by_call_id: dict[UUID, UUID] = {}

    async def authorize_tool_call(
        self,
        request: ToolCallAuthorizationRequest,
    ) -> ToolCallAuthorizationResponse:
        tool_call_id = uuid4()
        self.tool_by_call_id[tool_call_id] = request.tool_id
        self.run_by_call_id[tool_call_id] = request.run_id
        return ToolCallAuthorizationResponse(
            id=tool_call_id,
            run_id=request.run_id,
            workflow_id=request.workflow_id,
            tool_id=request.tool_id,
            status="pending",
            execution_state="authorized_not_executed",
            risk_class="read",
            policy_decision=ToolPolicyDecisionSummary(
                allowed=True,
                requires_approval=False,
                decision_id=f"decision-{request.tool_id}",
                reason_codes=[],
            ),
        )

    async def execute_tool_call(
        self,
        tool_call_id: UUID,
        request: ToolCallExecutionRequest,
    ) -> ToolCallExecutionResponse:
        tool_id = self.tool_by_call_id[tool_call_id]
        if tool_id == "observability_log_search":
            output_payload: dict[str, Any] = {
                "events": [
                    {
                        "event_id": "log-1",
                        "timestamp": "2026-07-15T07:00:00+00:00",
                        "severity": "error",
                        "service": "checkout-api",
                        "message": "raw log message should not be persisted as metadata",
                        "source_uri": "https://observability.example/events/log-1",
                    }
                ]
            }
        elif tool_id == "deployment_event_search":
            output_payload = {
                "deployments": [
                    {
                        "deployment_id": "dep-1",
                        "environment": "production",
                        "deployed_at": "2026-07-15T06:50:00+00:00",
                        "commit_sha": "abc123",
                        "status": "succeeded",
                        "source_uri": "https://deployments.example/events/dep-1",
                    }
                ]
            }
        else:
            output_payload = {
                "path": request.input_payload["path"],
                "ref": request.input_payload["ref"],
                "content": "secret = 'not metadata'\n",
                "sha": "file-sha-1",
            }
        return ToolCallExecutionResponse(
            id=tool_call_id,
            run_id=self.run_by_call_id[tool_call_id],
            workflow_id="incident_response_investigator",
            tool_id=tool_id,
            status="succeeded",
            execution_state="executed",
            output_hash="hash",
            output_payload=output_payload,
            latency_ms=8,
        )


class UngroundedIncidentToolRuntime(FakeIncidentToolRuntime):
    async def execute_tool_call(
        self,
        tool_call_id: UUID,
        request: ToolCallExecutionRequest,
    ) -> ToolCallExecutionResponse:
        response = await super().execute_tool_call(tool_call_id, request)
        if response.tool_id == "observability_log_search":
            response.output_payload["events"][0].pop("source_uri", None)
        return response


class RuntimeSession:
    def __init__(self, runs: dict[UUID, WorkflowRun]) -> None:
        self.runs = runs
        self.added: list[object] = []
        self.flush_count = 0
        self.commit_count = 0

    def add(self, instance: object) -> None:
        self.added.append(instance)

    def flush(self) -> None:
        self.flush_count += 1

    def commit(self) -> None:
        self.commit_count += 1

    def get(self, model: object, identifier: object) -> object | None:
        if model is WorkflowRun:
            return self.runs.get(cast(UUID, identifier))
        return None


def create_live_incident_run(input_payload: dict[str, Any] | None = None) -> WorkflowRun:
    return WorkflowRun(
        id=uuid4(),
        workflow_id="incident_response_investigator",
        registry_snapshot_id=uuid4(),
        status="queued",
        execution_mode="live",
        autonomy_level="read_only",
        input_payload=input_payload
        if input_payload is not None
        else {
            "incident_id": "inc-001",
            "service": "checkout-api",
            "time_window": {
                "start": "2026-07-15T06:45:00+00:00",
                "end": "2026-07-15T07:15:00+00:00",
            },
            "severity": "error",
            "environment": "production",
            "repository": "acme/checkout",
            "ref": "main",
            "suspect_paths": ["services/checkout/config.py"],
        },
        budget={"max_tool_calls": 25, "max_run_seconds": 300, "max_estimated_usd": 1.0},
        policy_context={},
    )


@pytest.mark.asyncio
async def test_collect_incident_evidence_runs_graph_and_persists_metadata_only() -> None:
    run = create_live_incident_run()
    session = RuntimeSession({run.id: run})

    response = await collect_incident_evidence(
        run_id=run.id,
        request=IncidentInvestigationRequest(actor_id="user-123", trace_id="trace-1"),
        session=cast(Session, session),
        workflow_registry=cast(WorkflowRegistry, object()),
        tool_registry=cast(ToolRegistry, object()),
        policy_evaluator=FakeToolPolicyEvaluator(),
        adapter_registry=ToolAdapterRegistry({}),
        available_connectors={"observability", "deployments", "github"},
        tool_runtime=FakeIncidentToolRuntime(),
    )

    assert run.status == "running"
    assert response.stage == "incident_evidence_collected"
    assert response.incident_id == "inc-001"
    assert response.log_event_count == 1
    assert response.deployment_event_count == 1
    assert response.code_file_count == 1
    assert response.rca_generation_enabled is False
    assert response.write_actions_enabled is False
    assert response.evidence_validation.grounded is True
    assert response.evidence_validation.evidence_count == 3
    assert response.rca_draft_created is False
    assert response.rca_draft is None
    assert response.policy_decision_ids == [
        "decision-observability_log_search",
        "decision-deployment_event_search",
        "decision-github_file_read",
    ]
    evidence_records = [item for item in session.added if isinstance(item, EvidenceRecord)]
    assert {record.kind for record in evidence_records} == {"log", "api_response", "code"}
    metadata_payloads = [record.evidence_metadata for record in evidence_records]
    assert all("message" not in metadata for metadata in metadata_payloads)
    assert all("content" not in metadata for metadata in metadata_payloads)
    assert {metadata["evidence_kind"] for metadata in metadata_payloads} == {
        "observability_log_event",
        "deployment_event",
        "github_file",
    }
    assert session.commit_count == 1
    assert len([item for item in session.added if isinstance(item, AuditEvent)]) == 2


@pytest.mark.asyncio
async def test_collect_incident_evidence_creates_grounded_rca_draft_contract() -> None:
    run = create_live_incident_run()
    session = RuntimeSession({run.id: run})

    response = await collect_incident_evidence(
        run_id=run.id,
        request=IncidentInvestigationRequest(
            actor_id="user-123",
            trace_id="trace-1",
            include_rca=True,
        ),
        session=cast(Session, session),
        workflow_registry=cast(WorkflowRegistry, object()),
        tool_registry=cast(ToolRegistry, object()),
        policy_evaluator=FakeToolPolicyEvaluator(),
        adapter_registry=ToolAdapterRegistry({}),
        available_connectors={"observability", "deployments", "github"},
        tool_runtime=FakeIncidentToolRuntime(),
    )

    assert response.stage == "incident_rca_draft_created"
    assert response.evidence_validation.grounded is True
    assert response.rca_draft_created is True
    assert response.rca_draft is not None
    assert response.rca_draft.schema_version == "incident_response_investigator.rca_draft.v1"
    assert response.rca_draft.write_actions_enabled is False
    assert response.rca_draft.requires_human_review is True
    assert response.rca_draft.approval_required_for == [
        "rollback",
        "incident_update",
        "paging_action",
    ]
    allowed_uris = set(response.rca_draft.source_evidence_uris)
    assert allowed_uris
    assert all(
        set(claim.evidence_uris).issubset(allowed_uris)
        for claim in response.rca_draft.claims
    )
    evidence_records = [item for item in session.added if isinstance(item, EvidenceRecord)]
    assert len(evidence_records) == 4
    rca_records = [
        record
        for record in evidence_records
        if record.evidence_metadata.get("schema_version")
        == "incident_response_investigator.rca_draft.v1"
    ]
    assert len(rca_records) == 1
    assert rca_records[0].source_system == "aegisops"
    assert rca_records[0].evidence_metadata["write_actions_enabled"] is False
    audit_events = [item for item in session.added if isinstance(item, AuditEvent)]
    assert audit_events[-1].event_type == "workflow_graph.rca_draft_created"
    assert audit_events[-1].payload["rca_draft_created"] is True


@pytest.mark.asyncio
async def test_collect_incident_evidence_rejects_rca_for_ungrounded_evidence() -> None:
    run = create_live_incident_run()
    session = RuntimeSession({run.id: run})

    with pytest.raises(IncidentInvestigationRejectedError, match="RCA draft creation requires"):
        await collect_incident_evidence(
            run_id=run.id,
            request=IncidentInvestigationRequest(include_rca=True),
            session=cast(Session, session),
            workflow_registry=cast(WorkflowRegistry, object()),
            tool_registry=cast(ToolRegistry, object()),
            policy_evaluator=FakeToolPolicyEvaluator(),
            adapter_registry=ToolAdapterRegistry({}),
            available_connectors={"observability", "deployments", "github"},
            tool_runtime=UngroundedIncidentToolRuntime(),
        )

    assert run.status == "failed"
    assert session.commit_count == 1
    assert not any(isinstance(item, EvidenceRecord) for item in session.added)
    audit_events = [item for item in session.added if isinstance(item, AuditEvent)]
    assert audit_events[-1].event_type == "workflow_graph.failed"


@pytest.mark.asyncio
async def test_collect_incident_evidence_rejects_missing_input() -> None:
    run = create_live_incident_run(input_payload={})
    session = RuntimeSession({run.id: run})

    with pytest.raises(IncidentInvestigationRejectedError, match="incident_id"):
        await collect_incident_evidence(
            run_id=run.id,
            request=IncidentInvestigationRequest(),
            session=cast(Session, session),
            workflow_registry=cast(WorkflowRegistry, object()),
            tool_registry=cast(ToolRegistry, object()),
            policy_evaluator=FakeToolPolicyEvaluator(),
            adapter_registry=ToolAdapterRegistry({}),
            available_connectors={"observability", "deployments", "github"},
            tool_runtime=FakeIncidentToolRuntime(),
        )

    assert run.status == "failed"
    assert session.commit_count == 1


@pytest.mark.asyncio
async def test_collect_incident_evidence_uses_captured_replay_fixture(tmp_path: Path) -> None:
    run = create_live_incident_run()
    run.execution_mode = "replay"
    run.input_payload = {"replay_source_run_id": "captured-incident-run-001"}
    session = RuntimeSession({run.id: run})
    write_replay_fixture(tmp_path, "captured-incident-run-001")

    response = await collect_incident_evidence(
        run_id=run.id,
        request=IncidentInvestigationRequest(actor_id="user-123"),
        session=cast(Session, session),
        workflow_registry=cast(WorkflowRegistry, object()),
        tool_registry=cast(ToolRegistry, object()),
        policy_evaluator=FakeToolPolicyEvaluator(),
        adapter_registry=ToolAdapterRegistry({}),
        available_connectors={"observability", "deployments", "github"},
        replay_fixture_dir=tmp_path,
    )

    assert run.status == "running"
    assert response.stage == "incident_evidence_collected"
    assert response.incident_id == "inc-captured-001"
    assert response.log_event_count == 1
    assert response.deployment_event_count == 1
    assert response.code_file_count == 1
    assert response.tool_call_ids == [
        "captured-log-call",
        "captured-deployment-call",
        "captured-code-call",
    ]
    assert response.policy_decision_ids == [
        "captured-log-policy",
        "captured-deployment-policy",
        "captured-code-policy",
    ]
    assert response.evidence_validation.grounded is True
    assert response.evidence_validation.evidence_count == 3
    assert response.rca_draft_created is False
    assert len([item for item in session.added if isinstance(item, EvidenceRecord)]) == 3
    assert session.commit_count == 1


@pytest.mark.asyncio
async def test_collect_incident_evidence_rejects_replay_input_override(tmp_path: Path) -> None:
    run = create_live_incident_run()
    run.execution_mode = "replay"
    run.input_payload = {"replay_source_run_id": "captured-incident-run-001"}
    session = RuntimeSession({run.id: run})
    write_replay_fixture(tmp_path, "captured-incident-run-001")

    with pytest.raises(IncidentInvestigationRejectedError, match="captured replay fixture"):
        await collect_incident_evidence(
            run_id=run.id,
            request=IncidentInvestigationRequest(service="different-service"),
            session=cast(Session, session),
            workflow_registry=cast(WorkflowRegistry, object()),
            tool_registry=cast(ToolRegistry, object()),
            policy_evaluator=FakeToolPolicyEvaluator(),
            adapter_registry=ToolAdapterRegistry({}),
            available_connectors={"observability", "deployments", "github"},
            replay_fixture_dir=tmp_path,
        )

    assert run.status == "failed"
    assert session.commit_count == 1


@pytest.mark.asyncio
async def test_collect_incident_evidence_reports_missing_replay_fixture(tmp_path: Path) -> None:
    run = create_live_incident_run()
    run.execution_mode = "replay"
    run.input_payload = {"replay_source_run_id": "missing-incident-run"}
    session = RuntimeSession({run.id: run})

    with pytest.raises(ReplayFixtureError, match="Replay fixture was not found"):
        await collect_incident_evidence(
            run_id=run.id,
            request=IncidentInvestigationRequest(),
            session=cast(Session, session),
            workflow_registry=cast(WorkflowRegistry, object()),
            tool_registry=cast(ToolRegistry, object()),
            policy_evaluator=FakeToolPolicyEvaluator(),
            adapter_registry=ToolAdapterRegistry({}),
            available_connectors={"observability", "deployments", "github"},
            replay_fixture_dir=tmp_path,
        )

    assert run.status == "failed"
    assert session.commit_count == 1


def test_incident_evidence_endpoint_returns_404_for_missing_run() -> None:
    missing_run_id = uuid4()

    def override_session() -> Any:
        yield cast(Session, RuntimeSession({}))

    async def override_policy() -> ToolPolicyEvaluator:
        return FakeToolPolicyEvaluator()

    def override_adapters() -> ToolAdapterRegistry:
        return ToolAdapterRegistry({})

    app.dependency_overrides[get_database_session] = override_session
    app.dependency_overrides[get_tool_policy_evaluator] = override_policy
    app.dependency_overrides[get_tool_adapter_registry] = override_adapters
    try:
        client = TestClient(app)
        response = client.post(
            f"/workflow-runs/{missing_run_id}/incident-response-investigator/evidence",
            json={},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json()["detail"]["reason_code"] == "workflow_run_not_found"


def write_replay_fixture(directory: Path, source_run_id: str) -> None:
    (directory / f"{source_run_id}.json").write_text(
        json.dumps(
            {
                "schema_version": "incident_response_investigator.replay.v1",
                "workflow_id": "incident_response_investigator",
                "provenance": "captured_real_run",
                "source_run_id": source_run_id,
                "captured_at": "2026-07-15T07:30:00+00:00",
                "incident_id": "inc-captured-001",
                "service": "checkout-api",
                "time_window": {
                    "start": "2026-07-15T06:45:00+00:00",
                    "end": "2026-07-15T07:15:00+00:00",
                },
                "severity": "error",
                "environment": "production",
                "repository": "acme/checkout",
                "ref": "main",
                "suspect_paths": ["services/checkout/config.py"],
                "log_events": [
                    {
                        "event_id": "captured-log-1",
                        "timestamp": "2026-07-15T07:00:00+00:00",
                        "severity": "error",
                        "service": "checkout-api",
                        "message": "captured real log text",
                        "source_uri": "https://observability.example/events/captured-log-1",
                    }
                ],
                "deployment_events": [
                    {
                        "deployment_id": "captured-dep-1",
                        "environment": "production",
                        "deployed_at": "2026-07-15T06:50:00+00:00",
                        "commit_sha": "abc123",
                        "status": "succeeded",
                        "source_uri": "https://deployments.example/events/captured-dep-1",
                    }
                ],
                "code_files": [
                    {
                        "path": "services/checkout/config.py",
                        "ref": "main",
                        "content": "timeout_ms = 250\n",
                        "sha": "file-sha-1",
                    }
                ],
                "log_tool_call_ids": ["captured-log-call"],
                "deployment_tool_call_ids": ["captured-deployment-call"],
                "code_tool_call_ids": ["captured-code-call"],
                "log_policy_decision_ids": ["captured-log-policy"],
                "deployment_policy_decision_ids": ["captured-deployment-policy"],
                "code_policy_decision_ids": ["captured-code-policy"],
                "data_policy": {
                    "fake_data_allowed": False,
                    "replay_allowed_from_real_runs": True,
                },
            }
        ),
        encoding="utf-8",
    )
