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
from aegisops_api.workflows.engineering_issue_to_pr.replay import ReplayFixtureError
from aegisops_api.workflows.engineering_issue_to_pr.runtime import (
    IssueToPrRunRejectedError,
    IssueToPrRunRequest,
    collect_engineering_issue_context,
    parse_github_issue_url,
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


class FakeIssueToPrToolRuntime:
    def __init__(self) -> None:
        self.tool_by_call_id: dict[UUID, str] = {}

    async def authorize_tool_call(
        self,
        request: ToolCallAuthorizationRequest,
    ) -> ToolCallAuthorizationResponse:
        tool_call_id = uuid4()
        self.tool_by_call_id[tool_call_id] = request.tool_id
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
        if tool_id == "github_issue_read":
            output_payload = {
                "title": "Type checker failure in CI",
                "body": "CI fails during static analysis.",
                "labels": ["bug"],
                "author": "maintainer",
                "url": "https://github.com/acme/app/issues/42",
            }
        else:
            output_payload = {
                "path": request.input_payload["path"],
                "ref": request.input_payload["ref"],
                "content": "def handler():\n    return 'ok'\n",
                "sha": "abc123",
            }
        return ToolCallExecutionResponse(
            id=tool_call_id,
            run_id=uuid4(),
            workflow_id="engineering_issue_to_pr",
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


def create_live_engineering_run(input_payload: dict[str, Any] | None = None) -> WorkflowRun:
    return WorkflowRun(
        id=uuid4(),
        workflow_id="engineering_issue_to_pr",
        registry_snapshot_id=uuid4(),
        status="queued",
        execution_mode="live",
        autonomy_level="draft_only",
        input_payload=input_payload
        or {
            "issue_url": "https://github.com/acme/app/issues/42",
            "ref": "main",
            "context_paths": ["src/service.py"],
        },
        budget={"max_tool_calls": 25, "max_run_seconds": 300, "max_estimated_usd": 1.0},
        policy_context={},
    )


@pytest.mark.asyncio
async def test_collect_engineering_issue_context_runs_graph_and_persists_evidence() -> None:
    run = create_live_engineering_run()
    session = RuntimeSession({run.id: run})

    response = await collect_engineering_issue_context(
        run_id=run.id,
        request=IssueToPrRunRequest(actor_id="user-123", trace_id="trace-1"),
        session=cast(Session, session),
        workflow_registry=cast(WorkflowRegistry, object()),
        tool_registry=cast(ToolRegistry, object()),
        policy_evaluator=FakeToolPolicyEvaluator(),
        adapter_registry=ToolAdapterRegistry({}),
        available_connectors={"github"},
        tool_runtime=FakeIssueToPrToolRuntime(),
    )

    assert run.status == "running"
    assert response.stage == "issue_context_collected"
    assert response.issue_title == "Type checker failure in CI"
    assert response.context_file_count == 1
    assert response.policy_decision_ids == [
        "decision-github_issue_read",
        "decision-github_file_read",
    ]
    assert len(response.evidence_records) == 2
    assert {record.kind for record in response.evidence_records} == {"api_response", "code"}
    assert session.commit_count == 1
    assert len([item for item in session.added if isinstance(item, EvidenceRecord)]) == 2
    assert len([item for item in session.added if isinstance(item, AuditEvent)]) == 2


@pytest.mark.asyncio
async def test_collect_engineering_issue_context_uses_captured_replay_fixture(
    tmp_path: Path,
) -> None:
    run = create_live_engineering_run()
    run.execution_mode = "replay"
    run.input_payload = {"replay_source_run_id": "captured-real-run-001"}
    session = RuntimeSession({run.id: run})
    write_replay_fixture(tmp_path, "captured-real-run-001")

    response = await collect_engineering_issue_context(
        run_id=run.id,
        request=IssueToPrRunRequest(actor_id="user-123"),
        session=cast(Session, session),
        workflow_registry=cast(WorkflowRegistry, object()),
        tool_registry=cast(ToolRegistry, object()),
        policy_evaluator=FakeToolPolicyEvaluator(),
        adapter_registry=ToolAdapterRegistry({}),
        available_connectors={"github"},
        replay_fixture_dir=tmp_path,
    )

    assert run.status == "running"
    assert response.stage == "issue_context_collected"
    assert response.issue_title == "Captured issue from authorized run"
    assert response.policy_decision_ids == ["captured-policy-decision"]
    assert len(response.evidence_records) == 2
    assert session.commit_count == 1


@pytest.mark.asyncio
async def test_collect_engineering_issue_context_reports_missing_replay_fixture(
    tmp_path: Path,
) -> None:
    run = create_live_engineering_run()
    run.execution_mode = "replay"
    run.input_payload = {"replay_source_run_id": "missing-real-run"}
    session = RuntimeSession({run.id: run})

    with pytest.raises(ReplayFixtureError, match="Replay fixture was not found"):
        await collect_engineering_issue_context(
            run_id=run.id,
            request=IssueToPrRunRequest(),
            session=cast(Session, session),
            workflow_registry=cast(WorkflowRegistry, object()),
            tool_registry=cast(ToolRegistry, object()),
            policy_evaluator=FakeToolPolicyEvaluator(),
            adapter_registry=ToolAdapterRegistry({}),
            available_connectors={"github"},
            replay_fixture_dir=tmp_path,
        )

    assert run.status == "failed"
    assert session.commit_count == 1


def test_parse_github_issue_url_uses_structured_url_parts() -> None:
    assert parse_github_issue_url("https://github.com/acme/app/issues/42") == ("acme/app", 42)

    with pytest.raises(IssueToPrRunRejectedError):
        parse_github_issue_url("https://example.com/acme/app/issues/42")


def test_engineering_issue_context_endpoint_returns_404_for_missing_run() -> None:
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
            f"/workflow-runs/{missing_run_id}/engineering-issue-to-pr/evidence",
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
                "schema_version": "engineering_issue_to_pr.replay.v1",
                "workflow_id": "engineering_issue_to_pr",
                "provenance": "captured_real_run",
                "source_run_id": source_run_id,
                "captured_at": "2026-07-14T00:00:00+00:00",
                "repository": "acme/app",
                "issue_number": 42,
                "ref": "main",
                "issue": {
                    "title": "Captured issue from authorized run",
                    "body": "Captured issue body from an authorized real run.",
                    "labels": ["bug"],
                    "author": "maintainer",
                    "url": "https://github.com/acme/app/issues/42",
                },
                "context_files": [
                    {
                        "path": "src/service.py",
                        "ref": "main",
                        "content": "def handler():\n    return 'ok'\n",
                        "sha": "abc123",
                    }
                ],
                "tool_call_ids": ["captured-tool-call"],
                "policy_decision_ids": ["captured-policy-decision"],
                "data_policy": {
                    "fake_data_allowed": False,
                    "replay_allowed_from_real_runs": True,
                },
            }
        ),
        encoding="utf-8",
    )
