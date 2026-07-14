from pathlib import Path
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from aegisops_api.config import Settings
from aegisops_api.db.models import AuditEvent, WorkflowRegistrySnapshot, WorkflowRun
from aegisops_api.main import app, get_database_session, get_run_policy_evaluator
from aegisops_api.policy import PolicyDecision
from aegisops_api.workflows.registry import WorkflowRegistry
from aegisops_api.workflows.runs import (
    BudgetEnvelope,
    RunPolicyEvaluator,
    WorkflowRunStartRejectedError,
    WorkflowRunStartRequest,
    start_workflow_run,
)


class ScalarResult:
    def __init__(self, value: object | None) -> None:
        self._value = value

    def scalar_one_or_none(self) -> object | None:
        return self._value


class RecordingSession:
    def __init__(self, existing_snapshot: WorkflowRegistrySnapshot | None = None) -> None:
        self.existing_snapshot = existing_snapshot
        self.added: list[object] = []
        self.flush_count = 0
        self.commit_count = 0
        self.rollback_count = 0
        self.execute_count = 0

    def execute(self, _statement: object) -> ScalarResult:
        self.execute_count += 1
        return ScalarResult(self.existing_snapshot)

    def add(self, instance: object) -> None:
        self.added.append(instance)

    def flush(self) -> None:
        self.flush_count += 1

    def commit(self) -> None:
        self.commit_count += 1

    def rollback(self) -> None:
        self.rollback_count += 1


class FakeRunPolicyEvaluator:
    def __init__(self, decision: PolicyDecision) -> None:
        self.decision = decision
        self.inputs: list[dict[str, Any]] = []

    async def evaluate(self, input_payload: dict[str, Any]) -> PolicyDecision:
        self.inputs.append(input_payload)
        return self.decision


def create_ready_registry(tmp_path: Path) -> WorkflowRegistry:
    config_path = tmp_path / "ready_engineering.yaml"
    config_path.write_text(
        "\n".join(
            [
                "id: ready_engineering",
                "name: Ready Engineering Agent",
                "domain: engineering",
                "status: ready",
                "enabled_when:",
                "  connectors: [github]",
                "  required_scopes: [issues:read]",
                "patterns: [plan_execute]",
                "data_policy:",
                "  fake_data_allowed: false",
                "  replay_allowed_from_real_runs: true",
                "  regex_business_extraction_allowed: false",
                "default_autonomy: draft_only",
                "approval_required_for: [pull_request_creation]",
                "visual_surfaces: [executive_summary]",
            ]
        ),
        encoding="utf-8",
    )
    return WorkflowRegistry.from_directory(tmp_path)


@pytest.mark.asyncio
async def test_start_workflow_run_persists_replay_run_after_policy_allow(
    tmp_path: Path,
) -> None:
    registry = create_ready_registry(tmp_path)
    recording_session = RecordingSession()
    evaluator = FakeRunPolicyEvaluator(
        PolicyDecision(
            package_path="aegisops.run_eligibility",
            allowed=True,
            requires_approval=False,
            decision_id="decision-123",
            reason_codes=[],
            result={"allow": True, "requires_approval": False, "reason_codes": []},
        )
    )

    response = await start_workflow_run(
        request=WorkflowRunStartRequest(
            workflow_id="ready_engineering",
            replay_source_run_id="captured-real-run-001",
            user_id="user-123",
            input_payload={"issue_url": "https://github.com/example/repo/issues/1"},
        ),
        registry=registry,
        session=cast(Session, recording_session),
        policy_evaluator=evaluator,
        available_connectors={"github"},
        settings=Settings(),
    )

    assert response.status == "queued"
    assert response.workflow_id == "ready_engineering"
    assert response.policy_decision.decision_id == "decision-123"
    assert recording_session.commit_count == 1
    assert recording_session.rollback_count == 0
    assert any(isinstance(item, WorkflowRegistrySnapshot) for item in recording_session.added)
    assert any(isinstance(item, WorkflowRun) for item in recording_session.added)
    assert any(isinstance(item, AuditEvent) for item in recording_session.added)
    assert evaluator.inputs[0]["replay_source_run_id"] == "captured-real-run-001"
    assert evaluator.inputs[0]["budget"]["max_tool_calls"] == 25


@pytest.mark.asyncio
async def test_start_workflow_run_queues_live_run_for_approval(tmp_path: Path) -> None:
    registry = create_ready_registry(tmp_path)
    recording_session = RecordingSession()
    evaluator = FakeRunPolicyEvaluator(
        PolicyDecision(
            package_path="aegisops.run_eligibility",
            allowed=False,
            requires_approval=True,
            decision_id="decision-live",
            reason_codes=["approval_required"],
            result={
                "allow": False,
                "requires_approval": True,
                "reason_codes": ["approval_required"],
            },
        )
    )

    response = await start_workflow_run(
        request=WorkflowRunStartRequest(
            workflow_id="ready_engineering",
            execution_mode="live",
            budget=BudgetEnvelope(max_estimated_usd=0.5, max_tool_calls=10, max_run_seconds=120),
        ),
        registry=registry,
        session=cast(Session, recording_session),
        policy_evaluator=evaluator,
        available_connectors={"github"},
        settings=Settings(live_workflow_runs_enabled=True),
    )

    assert response.status == "waiting_for_approval"
    assert response.policy_decision.requires_approval is True
    assert recording_session.commit_count == 1


@pytest.mark.asyncio
async def test_start_workflow_run_rejects_missing_replay_source_before_policy(
    tmp_path: Path,
) -> None:
    registry = create_ready_registry(tmp_path)
    evaluator = FakeRunPolicyEvaluator(
        PolicyDecision(
            package_path="aegisops.run_eligibility",
            allowed=True,
            result={"allow": True},
        )
    )

    with pytest.raises(WorkflowRunStartRejectedError, match="Replay mode requires"):
        await start_workflow_run(
            request=WorkflowRunStartRequest(workflow_id="ready_engineering"),
            registry=registry,
            session=cast(Session, RecordingSession()),
            policy_evaluator=evaluator,
            available_connectors={"github"},
            settings=Settings(),
        )

    assert evaluator.inputs == []


@pytest.mark.asyncio
async def test_start_workflow_run_rejects_policy_denial_before_persistence(
    tmp_path: Path,
) -> None:
    registry = create_ready_registry(tmp_path)
    recording_session = RecordingSession()
    evaluator = FakeRunPolicyEvaluator(
        PolicyDecision(
            package_path="aegisops.run_eligibility",
            allowed=False,
            requires_approval=False,
            decision_id="decision-denied",
            reason_codes=["live_runs_disabled"],
            result={
                "allow": False,
                "requires_approval": False,
                "reason_codes": ["live_runs_disabled"],
            },
        )
    )

    with pytest.raises(WorkflowRunStartRejectedError, match="OPA policy denied"):
        await start_workflow_run(
            request=WorkflowRunStartRequest(
                workflow_id="ready_engineering",
                execution_mode="live",
            ),
            registry=registry,
            session=cast(Session, recording_session),
            policy_evaluator=evaluator,
            available_connectors={"github"},
            settings=Settings(),
        )

    assert recording_session.added == []
    assert recording_session.commit_count == 0


def test_workflow_run_endpoint_reports_planned_workflow_rejection() -> None:
    def override_session() -> Any:
        yield cast(Session, RecordingSession())

    async def override_policy() -> RunPolicyEvaluator:
        return FakeRunPolicyEvaluator(
            PolicyDecision(
                package_path="aegisops.run_eligibility",
                allowed=True,
                result={"allow": True},
            )
        )

    app.dependency_overrides[get_database_session] = override_session
    app.dependency_overrides[get_run_policy_evaluator] = override_policy
    try:
        client = TestClient(app)
        response = client.post(
            "/workflow-runs",
            json={
                "workflow_id": "engineering_issue_to_pr",
                "replay_source_run_id": "captured-real-run-001",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
    assert response.json()["detail"]["reason_code"] == "workflow_not_ready"
