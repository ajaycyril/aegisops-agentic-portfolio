from decimal import Decimal
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from aegisops_api.config import Settings
from aegisops_api.db.models import (
    Approval,
    AuditEvent,
    EvidenceRecord,
    MemoryRecord,
    ModelCall,
    ToolCall,
    WorkflowRegistrySnapshot,
    WorkflowRun,
    utc_now,
)
from aegisops_api.main import (
    app,
    get_database_session,
    get_run_policy_evaluator,
    live_run_admin_key_is_valid,
)
from aegisops_api.policy import PolicyDecision
from aegisops_api.workflows.registry import WorkflowRegistry
from aegisops_api.workflows.runs import (
    BudgetEnvelope,
    RunPolicyEvaluator,
    WorkflowRunStartRejectedError,
    WorkflowRunStartRequest,
    get_workflow_run_trace,
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


class ListResult:
    def __init__(self, values: list[object]) -> None:
        self._values = values

    def scalars(self) -> list[object]:
        return self._values


class TraceSession:
    def __init__(
        self,
        run: WorkflowRun | None,
        query_results: list[list[object]] | None = None,
    ) -> None:
        self.run = run
        self.query_results = query_results or []
        self.execute_count = 0

    def get(self, model: object, _identifier: object) -> object | None:
        if model is WorkflowRun:
            return self.run
        return None

    def execute(self, _statement: object) -> ListResult:
        result = self.query_results[self.execute_count]
        self.execute_count += 1
        return ListResult(result)


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


def test_get_workflow_run_trace_returns_metadata_records() -> None:
    now = utc_now()
    run = WorkflowRun(
        id=uuid4(),
        workflow_id="engineering_issue_to_pr",
        registry_snapshot_id=uuid4(),
        status="waiting_for_approval",
        execution_mode="live",
        autonomy_level="approval_required",
        input_payload={},
        budget={},
        policy_context={},
        started_at=now,
        updated_at=now,
    )
    approval = Approval(
        id=uuid4(),
        run_id=run.id,
        status="approved",
        risk_class="write",
        requested_action="pull_request_creation",
        requested_by="agent-runtime",
        approver_id="reviewer-123",
        requested_at=now,
        decided_at=now,
    )
    tool_call = ToolCall(
        id=uuid4(),
        run_id=run.id,
        approval_id=approval.id,
        tool_name="github_pull_request_draft",
        tool_version="schema-test",
        risk_class="write",
        input_schema_hash="schema",
        input_hash="input",
        status="pending",
        policy_decision_id="tool-policy",
        trace_id="trace-1",
        started_at=now,
        call_metadata={"execution_state": "authorized_not_executed"},
    )
    model_call = ModelCall(
        id=uuid4(),
        run_id=run.id,
        provider="openai",
        model="gpt-test",
        purpose="patch_plan",
        prompt_version="test.v1",
        input_token_count=0,
        output_token_count=0,
        estimated_cost_usd=Decimal("0"),
        status="succeeded",
        started_at=now,
    )
    evidence = EvidenceRecord(
        id=uuid4(),
        run_id=run.id,
        workflow_id=run.workflow_id,
        kind="document",
        source_system="aegisops",
        title="Dry-run PR preview",
        content_hash="content-hash",
        evidence_metadata={"schema_version": "engineering_issue_to_pr.pr_preview.v1"},
        captured_at=now,
        created_at=now,
    )
    memory = MemoryRecord(
        id=uuid4(),
        run_id=run.id,
        workflow_id=run.workflow_id,
        scope="run",
        subject_id=f"run:{run.id}",
        memory_key="customer_support.memory_policy",
        memory_value={"raw_customer_payload_persisted": False},
        retention_class="ephemeral_30d",
        data_sensitivity="confidential",
        created_at=now,
    )
    audit_event = AuditEvent(
        id=uuid4(),
        run_id=run.id,
        workflow_id=run.workflow_id,
        event_type="pr_draft.preview_created",
        actor_type="user",
        action="pr_draft.preview",
        data_sensitivity="internal",
        payload={"write_actions_enabled": False},
        created_at=now,
    )
    session = TraceSession(
        run,
        [[approval], [tool_call], [model_call], [evidence], [memory], [audit_event]],
    )

    response = get_workflow_run_trace(run.id, cast(Session, session))

    assert response.run.id == run.id
    assert response.run.status == "waiting_for_approval"
    assert response.approvals[0].status == "approved"
    assert response.tool_calls[0].execution_state == "authorized_not_executed"
    assert response.model_calls[0].estimated_cost_usd == "0"
    assert response.evidence_records[0].metadata["schema_version"].endswith("pr_preview.v1")
    assert response.memory_records[0].memory_key == "customer_support.memory_policy"
    assert response.memory_records[0].retention_class == "ephemeral_30d"
    assert response.audit_events[0].event_type == "pr_draft.preview_created"


def test_workflow_run_trace_endpoint_returns_404_for_missing_run() -> None:
    missing_run_id = uuid4()

    def override_session() -> Any:
        yield cast(Session, TraceSession(None))

    app.dependency_overrides[get_database_session] = override_session
    try:
        client = TestClient(app)
        response = client.get(f"/workflow-runs/{missing_run_id}/trace")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json()["detail"]["reason_code"] == "workflow_run_not_found"


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
        settings=Settings(live_workflow_runs_enabled=True, live_run_admin_key="admin-key"),
        live_run_authorized=True,
    )

    assert response.status == "waiting_for_approval"
    assert response.policy_decision.requires_approval is True
    assert recording_session.commit_count == 1
    assert evaluator.inputs[0]["admin_live_run_authorized"] is True


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
async def test_start_workflow_run_rejects_live_run_when_disabled_before_policy(
    tmp_path: Path,
) -> None:
    registry = create_ready_registry(tmp_path)
    recording_session = RecordingSession()
    evaluator = FakeRunPolicyEvaluator(
        PolicyDecision(
            package_path="aegisops.run_eligibility",
            allowed=True,
            result={"allow": True},
        )
    )

    with pytest.raises(WorkflowRunStartRejectedError) as exc_info:
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

    assert exc_info.value.reason_code == "live_runs_disabled"
    assert exc_info.value.http_status == 403
    assert evaluator.inputs == []
    assert recording_session.added == []
    assert recording_session.commit_count == 0


@pytest.mark.asyncio
async def test_start_workflow_run_rejects_live_run_without_admin_key_before_policy(
    tmp_path: Path,
) -> None:
    registry = create_ready_registry(tmp_path)
    recording_session = RecordingSession()
    evaluator = FakeRunPolicyEvaluator(
        PolicyDecision(
            package_path="aegisops.run_eligibility",
            allowed=True,
            result={"allow": True},
        )
    )

    with pytest.raises(WorkflowRunStartRejectedError) as exc_info:
        await start_workflow_run(
            request=WorkflowRunStartRequest(
                workflow_id="ready_engineering",
                execution_mode="live",
            ),
            registry=registry,
            session=cast(Session, recording_session),
            policy_evaluator=evaluator,
            available_connectors={"github"},
            settings=Settings(live_workflow_runs_enabled=True),
        )

    assert exc_info.value.reason_code == "live_run_admin_key_not_configured"
    assert exc_info.value.http_status == 503
    assert evaluator.inputs == []
    assert recording_session.added == []
    assert recording_session.commit_count == 0


@pytest.mark.asyncio
async def test_start_workflow_run_rejects_live_run_without_admin_authorization_before_policy(
    tmp_path: Path,
) -> None:
    registry = create_ready_registry(tmp_path)
    recording_session = RecordingSession()
    evaluator = FakeRunPolicyEvaluator(
        PolicyDecision(
            package_path="aegisops.run_eligibility",
            allowed=True,
            result={"allow": True},
        )
    )

    with pytest.raises(WorkflowRunStartRejectedError) as exc_info:
        await start_workflow_run(
            request=WorkflowRunStartRequest(
                workflow_id="ready_engineering",
                execution_mode="live",
            ),
            registry=registry,
            session=cast(Session, recording_session),
            policy_evaluator=evaluator,
            available_connectors={"github"},
            settings=Settings(live_workflow_runs_enabled=True, live_run_admin_key="admin-key"),
        )

    assert exc_info.value.reason_code == "live_run_admin_required"
    assert exc_info.value.http_status == 403
    assert evaluator.inputs == []
    assert recording_session.added == []
    assert recording_session.commit_count == 0


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
            reason_codes=["budget_exceeded"],
            result={
                "allow": False,
                "requires_approval": False,
                "reason_codes": ["budget_exceeded"],
            },
        )
    )

    with pytest.raises(WorkflowRunStartRejectedError, match="OPA policy denied"):
        await start_workflow_run(
            request=WorkflowRunStartRequest(
                workflow_id="ready_engineering",
                replay_source_run_id="captured-real-run-001",
            ),
            registry=registry,
            session=cast(Session, recording_session),
            policy_evaluator=evaluator,
            available_connectors={"github"},
            settings=Settings(),
        )

    assert recording_session.added == []
    assert recording_session.commit_count == 0


def test_live_run_admin_key_validator_requires_configured_matching_key() -> None:
    settings = Settings(live_run_admin_key="admin-key")

    assert live_run_admin_key_is_valid(settings, "admin-key") is True
    assert live_run_admin_key_is_valid(settings, "wrong-key") is False
    assert live_run_admin_key_is_valid(settings, None) is False
    assert live_run_admin_key_is_valid(Settings(), "admin-key") is False


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
