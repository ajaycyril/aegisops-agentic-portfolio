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

    assert session.commit_count == 0


@pytest.mark.asyncio
async def test_collect_incident_evidence_rejects_replay_until_captured_replay_exists() -> None:
    run = create_live_incident_run()
    run.execution_mode = "replay"
    session = RuntimeSession({run.id: run})

    with pytest.raises(IncidentInvestigationRejectedError, match="captured-real replay"):
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

    assert session.commit_count == 0


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
