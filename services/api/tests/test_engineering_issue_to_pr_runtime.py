import json
from pathlib import Path
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.orm import Session

from aegisops_api.db.models import Approval, AuditEvent, EvidenceRecord, WorkflowRun
from aegisops_api.main import (
    app,
    get_approval_policy_evaluator,
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
from aegisops_api.workflows.engineering_issue_to_pr.graph import (
    IssueToPrEvaluation,
    IssueToPrProposal,
    IssueToPrState,
    PlannedFileChange,
)
from aegisops_api.workflows.engineering_issue_to_pr.graph import (
    TestPlanStep as GraphTestPlanStep,
)
from aegisops_api.workflows.engineering_issue_to_pr.replay import ReplayFixtureError
from aegisops_api.workflows.engineering_issue_to_pr.runtime import (
    IssueToPrApprovalDecisionRequest,
    IssueToPrApprovalReviewRequest,
    IssueToPrPrDraftAuthorizationRequest,
    IssueToPrRunRejectedError,
    IssueToPrRunRequest,
    ProposedIssueToPrWriteAction,
    authorize_issue_to_pr_draft_pr,
    collect_engineering_issue_context,
    decide_issue_to_pr_approval,
    parse_github_issue_url,
    request_issue_to_pr_approval_review,
)
from aegisops_api.workflows.registry import WorkflowRegistry

TOOL_CONFIG_DIR = Path(__file__).resolve().parents[3] / "configs" / "tools"


class FakeToolPolicyEvaluator:
    def __init__(self, decision: PolicyDecision | None = None) -> None:
        self.decision = decision or PolicyDecision(
            package_path="aegisops.tool_access",
            allowed=True,
            requires_approval=False,
            decision_id="decision-runtime",
            reason_codes=[],
            result={"allow": True},
        )
        self.inputs: list[dict[str, Any]] = []

    async def evaluate(self, input_payload: dict[str, Any]) -> PolicyDecision:
        self.inputs.append(input_payload)
        return self.decision


class FakeApprovalPolicyEvaluator:
    def __init__(self, decision: PolicyDecision | None = None) -> None:
        self.decision = decision or PolicyDecision(
            package_path="aegisops.approvals",
            allowed=True,
            requires_approval=True,
            decision_id="approval-decision-runtime",
            reason_codes=[],
            result={"allow": True, "requires_approval": True, "reason_codes": []},
        )
        self.inputs: list[dict[str, Any]] = []

    async def evaluate(self, input_payload: dict[str, Any]) -> PolicyDecision:
        self.inputs.append(input_payload)
        return self.decision


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


class FakeIssueToPrPlanner:
    async def create_patch_plan(self, state: IssueToPrState) -> IssueToPrProposal:
        return IssueToPrProposal(
            summary="Plan from captured evidence.",
            problem_statement=str(state["issue"]["title"]),
            source_evidence_uris=[item["source_uri"] for item in state["evidence"]],
            planned_changes=[],
            test_plan=[],
            risk_notes=["No write action is enabled."],
        )

    async def evaluate_patch_plan(
        self,
        _state: IssueToPrState,
        proposal: IssueToPrProposal,
    ) -> IssueToPrEvaluation:
        return IssueToPrEvaluation(
            grounded=bool(proposal.source_evidence_uris),
            requires_more_context=True,
            risk_level="medium",
            findings=["Proposal is grounded but needs implementation context."],
            blocking_issues=[],
        )


class RuntimeSession:
    def __init__(
        self,
        runs: dict[UUID, WorkflowRun],
        approvals: dict[UUID, Approval] | None = None,
    ) -> None:
        self.runs = runs
        self.approvals = approvals or {}
        self.added: list[object] = []
        self.flush_count = 0
        self.commit_count = 0
        self.rollback_count = 0

    def add(self, instance: object) -> None:
        self.added.append(instance)

    def flush(self) -> None:
        self.flush_count += 1

    def commit(self) -> None:
        self.commit_count += 1

    def rollback(self) -> None:
        self.rollback_count += 1

    def get(self, model: object, identifier: object) -> object | None:
        if model is WorkflowRun:
            return self.runs.get(cast(UUID, identifier))
        if model is Approval:
            return self.approvals.get(cast(UUID, identifier))
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


def create_ready_engineering_registry(tmp_path: Path) -> WorkflowRegistry:
    config_path = tmp_path / "engineering_issue_to_pr.yaml"
    config_path.write_text(
        "\n".join(
            [
                "id: engineering_issue_to_pr",
                "name: Ready Engineering Agent",
                "domain: engineering",
                "status: ready",
                "enabled_when:",
                "  connectors: [github]",
                "  required_scopes: [issues:read, contents:read, pull_requests:write]",
                "patterns: [plan_execute]",
                "data_policy:",
                "  fake_data_allowed: false",
                "  replay_allowed_from_real_runs: true",
                "  regex_business_extraction_allowed: false",
                "default_autonomy: approval_required",
                "approval_required_for: [branch_creation, pull_request_creation]",
                "visual_surfaces: [executive_summary]",
            ]
        ),
        encoding="utf-8",
    )
    return WorkflowRegistry.from_directory(tmp_path)


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
async def test_collect_engineering_issue_context_can_include_proposal_with_planner(
    tmp_path: Path,
) -> None:
    run = create_live_engineering_run()
    run.execution_mode = "replay"
    run.input_payload = {"replay_source_run_id": "captured-real-run-001"}
    session = RuntimeSession({run.id: run})
    write_replay_fixture(tmp_path, "captured-real-run-001")

    response = await collect_engineering_issue_context(
        run_id=run.id,
        request=IssueToPrRunRequest(include_proposal=True),
        session=cast(Session, session),
        workflow_registry=cast(WorkflowRegistry, object()),
        tool_registry=cast(ToolRegistry, object()),
        policy_evaluator=FakeToolPolicyEvaluator(),
        adapter_registry=ToolAdapterRegistry({}),
        available_connectors={"github"},
        replay_fixture_dir=tmp_path,
        planner=FakeIssueToPrPlanner(),
    )

    assert response.proposal is not None
    assert response.proposal["write_actions_enabled"] is False
    assert response.evaluation is not None
    assert response.evaluation["grounded"] is True


@pytest.mark.asyncio
async def test_collect_engineering_issue_context_rejects_proposal_without_planner() -> None:
    run = create_live_engineering_run()
    session = RuntimeSession({run.id: run})

    with pytest.raises(IssueToPrRunRejectedError, match="Proposal generation requires"):
        await collect_engineering_issue_context(
            run_id=run.id,
            request=IssueToPrRunRequest(include_proposal=True),
            session=cast(Session, session),
            workflow_registry=cast(WorkflowRegistry, object()),
            tool_registry=cast(ToolRegistry, object()),
            policy_evaluator=FakeToolPolicyEvaluator(),
            adapter_registry=ToolAdapterRegistry({}),
            available_connectors={"github"},
            tool_runtime=FakeIssueToPrToolRuntime(),
        )

    assert session.commit_count == 0


@pytest.mark.asyncio
async def test_request_issue_to_pr_approval_review_persists_pending_write_approvals() -> None:
    run = create_live_engineering_run()
    run.status = "running"
    session = RuntimeSession({run.id: run})

    response = await request_issue_to_pr_approval_review(
        run_id=run.id,
        request=create_approval_review_request(),
        session=cast(Session, session),
    )

    assert run.status == "waiting_for_approval"
    assert response.approval_state == "pending_human_review"
    assert response.execution_state == "approval_requested_no_write_execution"
    assert response.write_actions_enabled is False
    assert [approval.requested_action for approval in response.approvals] == [
        "branch_creation",
        "pull_request_creation",
    ]
    assert session.commit_count == 1
    assert session.rollback_count == 0
    persisted_approvals = [item for item in session.added if isinstance(item, Approval)]
    assert len(persisted_approvals) == 2
    assert all(approval.status == "pending" for approval in persisted_approvals)
    assert all(approval.risk_class == "write" for approval in persisted_approvals)
    assert all(
        approval.request_payload["schema_version"] == "engineering_issue_to_pr.approval_review.v1"
        for approval in persisted_approvals
    )
    assert all(
        approval.request_payload["approval_contract"]["write_actions_enabled"] is False
        for approval in persisted_approvals
    )
    assert len([item for item in session.added if isinstance(item, AuditEvent)]) == 3


@pytest.mark.asyncio
async def test_request_issue_to_pr_approval_review_requires_running_run() -> None:
    run = create_live_engineering_run()
    session = RuntimeSession({run.id: run})

    with pytest.raises(IssueToPrRunRejectedError, match="collect evidence before approval"):
        await request_issue_to_pr_approval_review(
            run_id=run.id,
            request=create_approval_review_request(),
            session=cast(Session, session),
        )

    assert run.status == "queued"
    assert session.commit_count == 0


def test_approval_review_rejects_action_evidence_outside_proposal() -> None:
    with pytest.raises(ValidationError, match="proposed action evidence"):
        IssueToPrApprovalReviewRequest(
            proposal=create_patch_proposal(),
            evaluation=create_plan_evaluation(),
            requested_by="reviewer-123",
            proposed_actions=[
                ProposedIssueToPrWriteAction(
                    action_type="branch_creation",
                    repository="acme/app",
                    proposed_branch_name="aegis/fix-type-check",
                    rationale="Prepare branch for the reviewed patch plan.",
                    evidence_uris=["https://github.com/acme/app/issues/404"],
                )
            ],
        )


@pytest.mark.asyncio
async def test_decide_issue_to_pr_approval_approves_pending_branch_action() -> None:
    run = create_live_engineering_run()
    run.status = "waiting_for_approval"
    approval = create_pending_approval(run)
    evaluator = FakeApprovalPolicyEvaluator()
    session = RuntimeSession({run.id: run}, {approval.id: approval})

    response = await decide_issue_to_pr_approval(
        run_id=run.id,
        approval_id=approval.id,
        request=IssueToPrApprovalDecisionRequest(
            decision="approve",
            approver_id="reviewer-456",
            decision_reason="Plan is grounded in the collected evidence.",
            actor_id="reviewer-456",
            trace_id="trace-decision",
        ),
        session=cast(Session, session),
        policy_evaluator=evaluator,
    )

    assert approval.status == "approved"
    assert approval.approver_id == "reviewer-456"
    assert approval.policy_decision_id == "approval-decision-runtime"
    assert approval.decision_payload["write_actions_enabled"] is False
    assert run.status == "waiting_for_approval"
    assert response.approval_status == "approved"
    assert response.execution_state == "approval_decision_recorded_no_write_execution"
    assert response.write_actions_enabled is False
    assert evaluator.inputs[0]["decision_action"] == "approve"
    assert evaluator.inputs[0]["approval"]["write_actions_enabled"] is False
    assert session.commit_count == 1
    assert len([item for item in session.added if isinstance(item, AuditEvent)]) == 1


@pytest.mark.asyncio
async def test_decide_issue_to_pr_approval_rejects_and_cancels_write_path() -> None:
    run = create_live_engineering_run()
    run.status = "waiting_for_approval"
    approval = create_pending_approval(run, requested_action="pull_request_creation")
    session = RuntimeSession({run.id: run}, {approval.id: approval})

    response = await decide_issue_to_pr_approval(
        run_id=run.id,
        approval_id=approval.id,
        request=IssueToPrApprovalDecisionRequest(
            decision="reject",
            approver_id="reviewer-456",
            decision_reason="The proposal needs more implementation context.",
        ),
        session=cast(Session, session),
        policy_evaluator=FakeApprovalPolicyEvaluator(),
    )

    assert approval.status == "rejected"
    assert run.status == "canceled"
    assert response.approval_status == "rejected"
    assert response.run_status == "canceled"
    assert session.commit_count == 1


@pytest.mark.asyncio
async def test_decide_issue_to_pr_approval_records_policy_denial() -> None:
    run = create_live_engineering_run()
    run.status = "waiting_for_approval"
    approval = create_pending_approval(run)
    session = RuntimeSession({run.id: run}, {approval.id: approval})
    evaluator = FakeApprovalPolicyEvaluator(
        PolicyDecision(
            package_path="aegisops.approvals",
            allowed=False,
            requires_approval=True,
            decision_id="approval-denied",
            reason_codes=["self_approval_not_allowed"],
            result={
                "allow": False,
                "requires_approval": True,
                "reason_codes": ["self_approval_not_allowed"],
            },
        )
    )

    with pytest.raises(IssueToPrRunRejectedError, match="OPA policy denied"):
        await decide_issue_to_pr_approval(
            run_id=run.id,
            approval_id=approval.id,
            request=IssueToPrApprovalDecisionRequest(
                decision="approve",
                approver_id="agent-runtime",
            ),
            session=cast(Session, session),
            policy_evaluator=evaluator,
        )

    assert approval.status == "pending"
    assert session.commit_count == 1
    assert len([item for item in session.added if isinstance(item, AuditEvent)]) == 1


@pytest.mark.asyncio
async def test_authorize_issue_to_pr_draft_pr_uses_approved_approval_id(
    tmp_path: Path,
) -> None:
    run = create_live_engineering_run()
    run.status = "waiting_for_approval"
    run.autonomy_level = "approval_required"
    approval = create_pending_approval(run, requested_action="pull_request_creation")
    approval.status = "approved"
    session = RuntimeSession({run.id: run}, {approval.id: approval})
    evaluator = FakeToolPolicyEvaluator()

    response = await authorize_issue_to_pr_draft_pr(
        run_id=run.id,
        request=create_pr_draft_authorization_request(approval.id),
        session=cast(Session, session),
        workflow_registry=create_ready_engineering_registry(tmp_path),
        tool_registry=ToolRegistry.from_directory(TOOL_CONFIG_DIR),
        policy_evaluator=evaluator,
        available_connectors={"github"},
    )

    assert response.status == "pending"
    assert response.execution_state == "authorized_not_executed"
    assert response.approval_id == approval.id
    assert response.execution_available is False
    assert response.write_actions_enabled is False
    assert evaluator.inputs[0]["approval"]["status"] == "approved"
    assert session.commit_count == 1


@pytest.mark.asyncio
async def test_authorize_issue_to_pr_draft_pr_blocks_without_approval_id(
    tmp_path: Path,
) -> None:
    run = create_live_engineering_run()
    run.status = "waiting_for_approval"
    run.autonomy_level = "approval_required"
    session = RuntimeSession({run.id: run})
    evaluator = FakeToolPolicyEvaluator(
        PolicyDecision(
            package_path="aegisops.tool_access",
            allowed=False,
            requires_approval=True,
            decision_id="tool-decision-approval-required",
            reason_codes=["approval_required"],
            result={
                "allow": False,
                "requires_approval": True,
                "reason_codes": ["approval_required"],
            },
        )
    )

    response = await authorize_issue_to_pr_draft_pr(
        run_id=run.id,
        request=create_pr_draft_authorization_request(),
        session=cast(Session, session),
        workflow_registry=create_ready_engineering_registry(tmp_path),
        tool_registry=ToolRegistry.from_directory(TOOL_CONFIG_DIR),
        policy_evaluator=evaluator,
        available_connectors={"github"},
    )

    assert response.status == "blocked"
    assert response.execution_state == "blocked_before_execution"
    assert response.policy_decision.requires_approval is True
    assert response.policy_decision.reason_codes == ["approval_required"]
    assert response.approval_id is None
    assert response.execution_available is False
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


def test_engineering_approval_decision_endpoint_records_approval() -> None:
    run = create_live_engineering_run()
    run.status = "waiting_for_approval"
    approval = create_pending_approval(run)
    runtime_session = RuntimeSession({run.id: run}, {approval.id: approval})

    def override_session() -> Any:
        yield cast(Session, runtime_session)

    async def override_policy() -> FakeApprovalPolicyEvaluator:
        return FakeApprovalPolicyEvaluator()

    app.dependency_overrides[get_database_session] = override_session
    app.dependency_overrides[get_approval_policy_evaluator] = override_policy
    try:
        client = TestClient(app)
        response = client.post(
            f"/workflow-runs/{run.id}/engineering-issue-to-pr/approvals/{approval.id}/decision",
            json={"decision": "approve", "approver_id": "reviewer-456"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["approval_status"] == "approved"
    assert approval.status == "approved"
    assert runtime_session.commit_count == 1


def create_approval_review_request() -> IssueToPrApprovalReviewRequest:
    return IssueToPrApprovalReviewRequest(
        proposal=create_patch_proposal(),
        evaluation=create_plan_evaluation(),
        requested_by="reviewer-123",
        actor_id="reviewer-123",
        trace_id="trace-approval",
        proposed_actions=[
            ProposedIssueToPrWriteAction(
                action_type="branch_creation",
                repository="acme/app",
                proposed_branch_name="aegis/fix-type-check",
                rationale="Prepare an isolated branch for the reviewed patch plan.",
                evidence_uris=[
                    "https://github.com/acme/app/issues/42",
                    "https://github.com/acme/app/blob/main/src/service.py",
                ],
            ),
            ProposedIssueToPrWriteAction(
                action_type="pull_request_creation",
                repository="acme/app",
                proposed_branch_name="aegis/fix-type-check",
                title="Fix CI type checker failure",
                rationale="Create a draft PR only after human approval is recorded.",
                evidence_uris=["https://github.com/acme/app/issues/42"],
            ),
        ],
    )


def create_pr_draft_authorization_request(
    approval_id: UUID | None = None,
) -> IssueToPrPrDraftAuthorizationRequest:
    return IssueToPrPrDraftAuthorizationRequest(
        repository="acme/app",
        title="Fix CI type checker failure",
        body="Draft PR body assembled from approved evidence and test plan.",
        head_branch="aegis/fix-type-check",
        base_branch="main",
        approval_id=approval_id,
        actor_id="reviewer-456",
        trace_id="trace-pr-draft",
    )


def create_patch_proposal() -> IssueToPrProposal:
    return IssueToPrProposal(
        summary="Fix the CI type checker failure.",
        problem_statement="The tracked issue reports a static analysis failure in CI.",
        source_evidence_uris=[
            "https://github.com/acme/app/issues/42",
            "https://github.com/acme/app/blob/main/src/service.py",
        ],
        planned_changes=[
            PlannedFileChange(
                path="src/service.py",
                change_type="modify",
                rationale="Align handler typing with the failing check.",
                evidence_uris=["https://github.com/acme/app/blob/main/src/service.py"],
            )
        ],
        test_plan=[
            GraphTestPlanStep(
                command="pnpm -r typecheck",
                purpose="Verify TypeScript contracts remain valid.",
                risk_covered="Static analysis regression.",
            )
        ],
        risk_notes=["No branch or pull request is created by the planner."],
    )


def create_plan_evaluation() -> IssueToPrEvaluation:
    return IssueToPrEvaluation(
        grounded=True,
        requires_more_context=False,
        risk_level="medium",
        findings=["Proposal cites the issue and repository file evidence."],
        blocking_issues=[],
    )


def create_pending_approval(
    run: WorkflowRun,
    requested_action: str = "branch_creation",
) -> Approval:
    return Approval(
        id=uuid4(),
        run_id=run.id,
        status="pending",
        risk_class="write",
        requested_action=requested_action,
        requested_by="agent-runtime",
        request_payload={
            "schema_version": "engineering_issue_to_pr.approval_review.v1",
            "proposal": create_patch_proposal().model_dump(mode="json"),
            "evaluation": create_plan_evaluation().model_dump(mode="json"),
            "proposed_action": {
                "action_type": requested_action,
                "repository": "acme/app",
                "base_ref": "main",
                "proposed_branch_name": "aegis/fix-type-check",
                "title": "Fix CI type checker failure",
                "rationale": "Human-reviewed write action proposal.",
                "evidence_uris": ["https://github.com/acme/app/issues/42"],
                "dry_run_only": True,
                "write_actions_enabled": False,
            },
            "approval_contract": {
                "approval_table": "approvals",
                "tool_call_approval_id_required": True,
                "write_actions_enabled": False,
                "dry_run_only": True,
            },
        },
        decision_payload={},
    )


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
