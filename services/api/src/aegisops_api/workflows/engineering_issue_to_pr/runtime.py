from __future__ import annotations

import json
from datetime import timedelta
from hashlib import sha256
from pathlib import Path
from typing import Any, Literal, Protocol, cast
from urllib.parse import urlparse
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.orm import Session

from aegisops_api.audit import AuditEventInput, write_audit_event
from aegisops_api.db.models import Approval, EvidenceRecord, WorkflowRun, utc_now
from aegisops_api.policy import OpaClient, PolicyDecision
from aegisops_api.tools import ToolPolicyEvaluator
from aegisops_api.tools.adapters import ToolAdapterRegistry
from aegisops_api.tools.registry import ToolRegistry
from aegisops_api.workflows.engineering_issue_to_pr.graph import (
    ENGINEERING_WORKFLOW_ID,
    IssueToPrEvaluation,
    IssueToPrGraphDependencies,
    IssueToPrGraphInput,
    IssueToPrPlanner,
    IssueToPrProposal,
    IssueToPrState,
    IssueToPrToolRuntime,
    PolicyBackedIssueToPrToolRuntime,
    as_issue_to_pr_state,
    create_engineering_issue_to_pr_graph,
)
from aegisops_api.workflows.engineering_issue_to_pr.replay import load_issue_to_pr_replay_fixture
from aegisops_api.workflows.registry import WorkflowRegistry

IssueToPrRunStage = Literal["issue_context_collected"]
IssueToPrApprovalActionType = Literal["branch_creation", "pull_request_creation"]
IssueToPrApprovalDecisionAction = Literal["approve", "reject"]
IssueToPrApprovalDecisionStatus = Literal["approved", "rejected"]


class IssueToPrRunRejectedError(RuntimeError):
    def __init__(self, reason_code: str, message: str, http_status: int = 409) -> None:
        super().__init__(message)
        self.reason_code = reason_code
        self.message = message
        self.http_status = http_status


class IssueToPrRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    repository: str | None = Field(default=None, min_length=1)
    issue_number: int | None = Field(default=None, gt=0)
    issue_url: str | None = Field(default=None, min_length=1)
    ref: str | None = Field(default=None, min_length=1)
    context_paths: list[str] | None = Field(default=None, max_length=10)
    actor_id: str | None = None
    trace_id: str | None = None
    include_proposal: bool = False

    @model_validator(mode="after")
    def validate_issue_locator(self) -> IssueToPrRunRequest:
        if self.issue_url is not None and (
            self.repository is not None or self.issue_number is not None
        ):
            raise ValueError("Use issue_url or repository plus issue_number, not both.")
        if (self.repository is None) != (self.issue_number is None):
            raise ValueError("repository and issue_number must be provided together.")
        return self


class EvidenceRecordSummary(BaseModel):
    id: UUID
    kind: str
    source_system: str
    source_uri: str | None
    title: str
    content_hash: str


class IssueToPrRunResponse(BaseModel):
    run_id: UUID
    workflow_id: str
    run_status: str
    stage: IssueToPrRunStage
    issue_title: str
    issue_url: str
    context_file_count: int
    tool_call_ids: list[str]
    evidence_records: list[EvidenceRecordSummary]
    policy_decision_ids: list[str]
    proposal: dict[str, Any] | None = None
    evaluation: dict[str, Any] | None = None


class ProposedIssueToPrWriteAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_type: IssueToPrApprovalActionType
    repository: str = Field(min_length=1)
    base_ref: str = Field(default="main", min_length=1)
    proposed_branch_name: str = Field(min_length=1)
    title: str | None = Field(default=None, min_length=1)
    rationale: str = Field(min_length=1)
    evidence_uris: list[str] = Field(min_length=1, max_length=20)
    dry_run_only: Literal[True] = True
    write_actions_enabled: Literal[False] = False

    @model_validator(mode="after")
    def validate_pr_title(self) -> ProposedIssueToPrWriteAction:
        if self.action_type == "pull_request_creation" and self.title is None:
            raise ValueError("pull_request_creation requires a title")
        return self


class IssueToPrApprovalReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    proposal: IssueToPrProposal
    evaluation: IssueToPrEvaluation | None = None
    proposed_actions: list[ProposedIssueToPrWriteAction] = Field(min_length=1, max_length=2)
    requested_by: str = Field(min_length=1)
    actor_id: str | None = None
    trace_id: str | None = None

    @model_validator(mode="after")
    def validate_actions_against_proposal(self) -> IssueToPrApprovalReviewRequest:
        action_types = [action.action_type for action in self.proposed_actions]
        if len(action_types) != len(set(action_types)):
            raise ValueError("proposed_actions must not contain duplicate action types")
        proposal_evidence = set(self.proposal.source_evidence_uris)
        for action in self.proposed_actions:
            missing_evidence = set(action.evidence_uris) - proposal_evidence
            if missing_evidence:
                raise ValueError("proposed action evidence must be present in proposal evidence")
        return self


class ApprovalReviewItem(BaseModel):
    id: UUID
    status: str
    requested_action: IssueToPrApprovalActionType
    risk_class: str
    requested_by: str
    requested_at: str
    expires_at: str
    write_actions_enabled: Literal[False] = False


class IssueToPrApprovalReviewResponse(BaseModel):
    run_id: UUID
    workflow_id: str
    run_status: str
    approval_state: Literal["pending_human_review"]
    approvals: list[ApprovalReviewItem]
    approval_table: Literal["approvals"] = "approvals"
    execution_state: Literal["approval_requested_no_write_execution"] = (
        "approval_requested_no_write_execution"
    )
    write_actions_enabled: Literal[False] = False


class IssueToPrApprovalDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: IssueToPrApprovalDecisionAction
    approver_id: str = Field(min_length=1)
    decision_reason: str | None = Field(default=None, min_length=1)
    actor_id: str | None = None
    trace_id: str | None = None


class ApprovalPolicyDecisionSummary(BaseModel):
    allowed: bool
    requires_approval: bool
    decision_id: str | None
    reason_codes: list[str]


class IssueToPrApprovalDecisionResponse(BaseModel):
    approval_id: UUID
    run_id: UUID
    workflow_id: str
    run_status: str
    requested_action: IssueToPrApprovalActionType
    approval_status: IssueToPrApprovalDecisionStatus
    approver_id: str
    decided_at: str
    policy_decision: ApprovalPolicyDecisionSummary
    execution_state: Literal["approval_decision_recorded_no_write_execution"] = (
        "approval_decision_recorded_no_write_execution"
    )
    write_actions_enabled: Literal[False] = False


class ApprovalPolicyEvaluator(Protocol):
    async def evaluate(self, input_payload: dict[str, Any]) -> PolicyDecision:
        pass


class OpaApprovalPolicyEvaluator:
    def __init__(self, opa_client: OpaClient) -> None:
        self._opa_client = opa_client

    async def evaluate(self, input_payload: dict[str, Any]) -> PolicyDecision:
        return await self._opa_client.evaluate("aegisops.approvals", input_payload)


async def collect_engineering_issue_context(
    run_id: UUID,
    request: IssueToPrRunRequest,
    session: Session,
    workflow_registry: WorkflowRegistry,
    tool_registry: ToolRegistry,
    policy_evaluator: ToolPolicyEvaluator,
    adapter_registry: ToolAdapterRegistry,
    available_connectors: set[str],
    tool_runtime: IssueToPrToolRuntime | None = None,
    planner: IssueToPrPlanner | None = None,
    replay_fixture_dir: Path | None = None,
) -> IssueToPrRunResponse:
    run = session.get(WorkflowRun, run_id)
    if run is None:
        raise IssueToPrRunRejectedError(
            reason_code="workflow_run_not_found",
            message="Workflow run was not found.",
            http_status=404,
        )
    ensure_run_can_collect_issue_context(run)
    if request.include_proposal and planner is None:
        raise IssueToPrRunRejectedError(
            reason_code="planner_not_configured",
            message=(
                "Proposal generation requires OPENAI_API_KEY and an explicit OpenAI model "
                "configuration."
            ),
            http_status=503,
        )

    try:
        run.status = "running"
        graph_state: IssueToPrState | None = None
        graph_input: IssueToPrGraphInput | None = None
        graph: Any | None = None
        if run.execution_mode == "replay":
            ensure_replay_request_does_not_override_fixture(request)
            graph_state = load_replay_graph_state(run, request, replay_fixture_dir)
            start_payload = {
                "stage": "issue_context_collection",
                "execution_mode": "replay",
                "replay_source_run_id": get_replay_source_run_id(run),
                "repository": graph_state["repository"],
                "issue_number": graph_state["issue_number"],
                "context_path_count": len(graph_state.get("context_paths", [])),
            }
        else:
            graph_input = build_graph_input_from_run(run, request)
            start_payload = {
                "stage": "issue_context_collection",
                "execution_mode": "live",
                "repository": graph_input.repository,
                "issue_number": graph_input.issue_number,
                "context_path_count": len(graph_input.context_paths),
            }
            runtime = tool_runtime or PolicyBackedIssueToPrToolRuntime(
                workflow_registry=workflow_registry,
                tool_registry=tool_registry,
                session=session,
                policy_evaluator=policy_evaluator,
                adapter_registry=adapter_registry,
                available_connectors=available_connectors,
            )
            graph = create_engineering_issue_to_pr_graph(
                IssueToPrGraphDependencies(
                    tool_runtime=runtime,
                    planner=planner if request.include_proposal else None,
                )
            )

        write_audit_event(
            session,
            AuditEventInput(
                run_id=run.id,
                workflow_id=run.workflow_id,
                event_type="workflow_graph.started",
                actor_type="user" if request.actor_id else "system",
                actor_id=request.actor_id,
                action="workflow_graph.collect_issue_context",
                resource_type="workflow_run",
                resource_id=str(run.id),
                trace_id=request.trace_id,
                payload=start_payload,
            ),
        )
        session.flush()
        if graph_state is None:
            if graph is None or graph_input is None:
                raise IssueToPrRunRejectedError(
                    reason_code="workflow_graph_not_initialized",
                    message="Workflow graph was not initialized.",
                )
            graph_state = as_issue_to_pr_state(await graph.ainvoke(graph_input.to_initial_state()))
        elif request.include_proposal and planner is not None:
            graph_state = await add_planner_outputs_to_graph_state(planner, graph_state)
        evidence_records = persist_graph_evidence(session, run, graph_state)
        policy_decision_ids = collect_tool_policy_decision_ids(graph_state)
        write_audit_event(
            session,
            AuditEventInput(
                run_id=run.id,
                workflow_id=run.workflow_id,
                event_type="workflow_graph.evidence_collected",
                actor_type="user" if request.actor_id else "system",
                actor_id=request.actor_id,
                action="workflow_graph.collect_issue_context",
                resource_type="workflow_run",
                resource_id=str(run.id),
                trace_id=request.trace_id,
                payload={
                    "stage": "issue_context_collected",
                    "evidence_count": len(evidence_records),
                    "tool_call_count": len(graph_state.get("tool_call_ids", [])),
                    "policy_decision_ids": policy_decision_ids,
                    "proposal_generated": "proposal" in graph_state,
                    "evaluation_generated": "evaluation" in graph_state,
                },
            ),
        )
        session.commit()
    except Exception as exc:
        run.status = "failed"
        run.failure_reason = str(exc)
        write_audit_event(
            session,
            AuditEventInput(
                run_id=run.id,
                workflow_id=run.workflow_id,
                event_type="workflow_graph.failed",
                actor_type="user" if request.actor_id else "system",
                actor_id=request.actor_id,
                action="workflow_graph.collect_issue_context",
                resource_type="workflow_run",
                resource_id=str(run.id),
                trace_id=request.trace_id,
                payload={"stage": "issue_context_collection", "error_type": type(exc).__name__},
            ),
        )
        session.commit()
        raise

    issue = graph_state["issue"]
    return IssueToPrRunResponse(
        run_id=run.id,
        workflow_id=run.workflow_id,
        run_status=run.status,
        stage="issue_context_collected",
        issue_title=str(issue["title"]),
        issue_url=str(issue["url"]),
        context_file_count=len(graph_state.get("context_files", [])),
        tool_call_ids=graph_state.get("tool_call_ids", []),
        evidence_records=[
            EvidenceRecordSummary(
                id=record.id,
                kind=record.kind,
                source_system=record.source_system,
                source_uri=record.source_uri,
                title=record.title,
                content_hash=record.content_hash,
            )
            for record in evidence_records
        ],
        policy_decision_ids=policy_decision_ids,
        proposal=graph_state.get("proposal"),
        evaluation=graph_state.get("evaluation"),
    )


async def request_issue_to_pr_approval_review(
    run_id: UUID,
    request: IssueToPrApprovalReviewRequest,
    session: Session,
) -> IssueToPrApprovalReviewResponse:
    run = session.get(WorkflowRun, run_id)
    if run is None:
        raise IssueToPrRunRejectedError(
            reason_code="workflow_run_not_found",
            message="Workflow run was not found.",
            http_status=404,
        )
    ensure_run_can_request_issue_to_pr_approval(run)

    requested_at = utc_now()
    expires_at = requested_at + timedelta(hours=24)
    approvals: list[Approval] = []
    try:
        run.status = "waiting_for_approval"
        for action in request.proposed_actions:
            approval = Approval(
                id=uuid4(),
                run_id=run.id,
                status="pending",
                risk_class="write",
                requested_action=action.action_type,
                requested_by=request.requested_by,
                request_payload={
                    "schema_version": "engineering_issue_to_pr.approval_review.v1",
                    "proposal": request.proposal.model_dump(mode="json"),
                    "evaluation": (
                        request.evaluation.model_dump(mode="json")
                        if request.evaluation is not None
                        else None
                    ),
                    "proposed_action": action.model_dump(mode="json"),
                    "approval_contract": {
                        "approval_table": "approvals",
                        "tool_call_approval_id_required": True,
                        "write_actions_enabled": False,
                        "dry_run_only": True,
                    },
                },
                decision_payload={},
                requested_at=requested_at,
                expires_at=expires_at,
            )
            session.add(approval)
            approvals.append(approval)
            write_audit_event(
                session,
                AuditEventInput(
                    run_id=run.id,
                    workflow_id=run.workflow_id,
                    event_type="approval.requested",
                    actor_type="user" if request.actor_id else "system",
                    actor_id=request.actor_id,
                    action="approval.request",
                    resource_type="approval",
                    resource_id=str(approval.id),
                    trace_id=request.trace_id,
                    payload={
                        "requested_action": action.action_type,
                        "risk_class": "write",
                        "requested_by": request.requested_by,
                        "write_actions_enabled": False,
                        "dry_run_only": True,
                    },
                ),
            )
        write_audit_event(
            session,
            AuditEventInput(
                run_id=run.id,
                workflow_id=run.workflow_id,
                event_type="workflow_run.waiting_for_approval",
                actor_type="user" if request.actor_id else "system",
                actor_id=request.actor_id,
                action="workflow_run.request_write_approval",
                resource_type="workflow_run",
                resource_id=str(run.id),
                trace_id=request.trace_id,
                payload={
                    "approval_count": len(approvals),
                    "requested_actions": [approval.requested_action for approval in approvals],
                    "write_actions_enabled": False,
                },
            ),
        )
        session.commit()
    except Exception:
        session.rollback()
        raise

    return IssueToPrApprovalReviewResponse(
        run_id=run.id,
        workflow_id=run.workflow_id,
        run_status=run.status,
        approval_state="pending_human_review",
        approvals=[
            ApprovalReviewItem(
                id=approval.id,
                status=approval.status,
                requested_action=cast(IssueToPrApprovalActionType, approval.requested_action),
                risk_class=approval.risk_class,
                requested_by=approval.requested_by,
                requested_at=approval.requested_at.isoformat(),
                expires_at=expires_at.isoformat(),
            )
            for approval in approvals
        ],
    )


async def decide_issue_to_pr_approval(
    run_id: UUID,
    approval_id: UUID,
    request: IssueToPrApprovalDecisionRequest,
    session: Session,
    policy_evaluator: ApprovalPolicyEvaluator,
) -> IssueToPrApprovalDecisionResponse:
    approval = session.get(Approval, approval_id)
    if approval is None:
        raise IssueToPrRunRejectedError(
            reason_code="approval_not_found",
            message="Approval record was not found.",
            http_status=404,
        )
    if approval.run_id != run_id:
        raise IssueToPrRunRejectedError(
            reason_code="approval_run_mismatch",
            message="Approval record does not belong to this workflow run.",
        )
    run = session.get(WorkflowRun, run_id)
    if run is None:
        raise IssueToPrRunRejectedError(
            reason_code="workflow_run_not_found",
            message="Workflow run was not found.",
            http_status=404,
        )
    ensure_approval_can_be_decided(run, approval)

    policy_input = build_approval_decision_policy_input(
        run=run,
        approval=approval,
        request=request,
    )
    decision = await policy_evaluator.evaluate(policy_input)
    if not decision.allowed:
        write_audit_event(
            session,
            AuditEventInput(
                run_id=run.id,
                workflow_id=run.workflow_id,
                event_type="approval.decision_blocked",
                actor_type="user" if request.actor_id else "system",
                actor_id=request.actor_id,
                action=f"approval.{request.decision}",
                resource_type="approval",
                resource_id=str(approval.id),
                policy_decision_id=decision.decision_id,
                trace_id=request.trace_id,
                payload={
                    "requested_action": approval.requested_action,
                    "policy_reason_codes": decision.reason_codes,
                    "write_actions_enabled": False,
                },
            ),
        )
        session.commit()
        raise IssueToPrRunRejectedError(
            reason_code="approval_decision_policy_denied",
            message="OPA policy denied the approval decision.",
            http_status=403,
        )

    decided_at = utc_now()
    approval.status = "approved" if request.decision == "approve" else "rejected"
    approval.approver_id = request.approver_id
    approval.policy_decision_id = decision.decision_id
    approval.decided_at = decided_at
    approval.decision_payload = {
        "schema_version": "engineering_issue_to_pr.approval_decision.v1",
        "decision": request.decision,
        "decision_reason": request.decision_reason,
        "approver_id": request.approver_id,
        "policy": {
            "decision_id": decision.decision_id,
            "package_path": decision.package_path,
            "reason_codes": decision.reason_codes,
            "result": decision.result,
        },
        "write_actions_enabled": False,
    }
    if request.decision == "reject":
        run.status = "canceled"
    write_audit_event(
        session,
        AuditEventInput(
            run_id=run.id,
            workflow_id=run.workflow_id,
            event_type=f"approval.{approval.status}",
            actor_type="user" if request.actor_id else "system",
            actor_id=request.actor_id,
            action=f"approval.{request.decision}",
            resource_type="approval",
            resource_id=str(approval.id),
            policy_decision_id=decision.decision_id,
            trace_id=request.trace_id,
            payload={
                "requested_action": approval.requested_action,
                "risk_class": approval.risk_class,
                "decision": request.decision,
                "run_status": run.status,
                "write_actions_enabled": False,
            },
        ),
    )
    session.commit()

    return IssueToPrApprovalDecisionResponse(
        approval_id=approval.id,
        run_id=run.id,
        workflow_id=run.workflow_id,
        run_status=run.status,
        requested_action=cast(IssueToPrApprovalActionType, approval.requested_action),
        approval_status=cast(IssueToPrApprovalDecisionStatus, approval.status),
        approver_id=request.approver_id,
        decided_at=decided_at.isoformat(),
        policy_decision=ApprovalPolicyDecisionSummary(
            allowed=decision.allowed,
            requires_approval=decision.requires_approval,
            decision_id=decision.decision_id,
            reason_codes=decision.reason_codes,
        ),
    )


def ensure_run_can_collect_issue_context(run: WorkflowRun) -> None:
    if run.workflow_id != ENGINEERING_WORKFLOW_ID:
        raise IssueToPrRunRejectedError(
            reason_code="workflow_not_supported",
            message="This runtime path only supports engineering_issue_to_pr runs.",
        )
    if run.status not in {"queued", "running"}:
        raise IssueToPrRunRejectedError(
            reason_code="workflow_run_not_executable",
            message=f"Workflow run status is {run.status}.",
        )
    if run.execution_mode != "live":
        if run.execution_mode == "replay":
            if get_replay_source_run_id(run) is None:
                raise IssueToPrRunRejectedError(
                    reason_code="replay_source_required",
                    message="Replay mode requires replay_source_run_id from a captured real run.",
                    http_status=422,
                )
            return
        raise IssueToPrRunRejectedError(
            reason_code="execution_mode_not_supported",
            message=f"Workflow run execution mode is {run.execution_mode}.",
        )


def ensure_run_can_request_issue_to_pr_approval(run: WorkflowRun) -> None:
    if run.workflow_id != ENGINEERING_WORKFLOW_ID:
        raise IssueToPrRunRejectedError(
            reason_code="workflow_not_supported",
            message="This runtime path only supports engineering_issue_to_pr runs.",
        )
    if run.status != "running":
        raise IssueToPrRunRejectedError(
            reason_code="workflow_run_not_ready_for_approval",
            message=(
                f"Workflow run status is {run.status}; collect evidence before approval review."
            ),
        )
    if run.execution_mode not in {"live", "replay"}:
        raise IssueToPrRunRejectedError(
            reason_code="execution_mode_not_supported",
            message=f"Workflow run execution mode is {run.execution_mode}.",
        )


def ensure_approval_can_be_decided(run: WorkflowRun, approval: Approval) -> None:
    if run.workflow_id != ENGINEERING_WORKFLOW_ID:
        raise IssueToPrRunRejectedError(
            reason_code="workflow_not_supported",
            message="This runtime path only supports engineering_issue_to_pr runs.",
        )
    if approval.requested_action not in {"branch_creation", "pull_request_creation"}:
        raise IssueToPrRunRejectedError(
            reason_code="approval_action_not_supported",
            message="This runtime path only supports branch and pull-request approvals.",
        )
    if approval.status != "pending":
        raise IssueToPrRunRejectedError(
            reason_code="approval_not_pending",
            message=f"Approval status is {approval.status}.",
        )
    if run.status != "waiting_for_approval":
        raise IssueToPrRunRejectedError(
            reason_code="workflow_run_not_waiting_for_approval",
            message=f"Workflow run status is {run.status}.",
        )


def build_approval_decision_policy_input(
    run: WorkflowRun,
    approval: Approval,
    request: IssueToPrApprovalDecisionRequest,
) -> dict[str, Any]:
    return {
        "workflow_id": run.workflow_id,
        "autonomy_level": run.autonomy_level,
        "decision_action": request.decision,
        "risk_class": approval.risk_class,
        "requested_action": approval.requested_action,
        "approver_id": request.approver_id,
        "approval": {
            "id": str(approval.id),
            "status": approval.status,
            "requested_by": approval.requested_by,
            "write_actions_enabled": extract_write_actions_enabled(approval.request_payload),
            "request_payload": approval.request_payload,
        },
    }


def extract_write_actions_enabled(request_payload: dict[str, Any]) -> bool:
    approval_contract = request_payload.get("approval_contract", {})
    if not isinstance(approval_contract, dict):
        return True
    return approval_contract.get("write_actions_enabled") is not False


def build_graph_input_from_run(
    run: WorkflowRun,
    request: IssueToPrRunRequest,
) -> IssueToPrGraphInput:
    payload = dict(run.input_payload or {})
    repository = request.repository
    issue_number = request.issue_number
    issue_url = request.issue_url
    if issue_url is None and repository is None and issue_number is None:
        issue_url = string_or_none(payload.get("issue_url"))
    if issue_url is not None:
        repository, issue_number = parse_github_issue_url(issue_url)
    if repository is None:
        repository = string_or_none(payload.get("repository"))
    if issue_number is None:
        issue_number = positive_int_or_none(payload.get("issue_number"))
    if repository is None or issue_number is None:
        raise IssueToPrRunRejectedError(
            reason_code="issue_locator_missing",
            message="Provide issue_url or repository plus issue_number.",
            http_status=422,
        )

    context_paths = request.context_paths
    if context_paths is None:
        context_paths = string_list_or_empty(payload.get("context_paths"))
    return IssueToPrGraphInput(
        run_id=run.id,
        repository=repository,
        issue_number=issue_number,
        ref=request.ref or string_or_none(payload.get("ref")) or "main",
        context_paths=context_paths,
        autonomy_level=cast(Any, run.autonomy_level),
        actor_id=request.actor_id or string_or_none(payload.get("actor_id")),
        trace_id=request.trace_id or string_or_none(payload.get("trace_id")),
    )


def load_replay_graph_state(
    run: WorkflowRun,
    request: IssueToPrRunRequest,
    replay_fixture_dir: Path | None,
) -> IssueToPrState:
    source_run_id = get_replay_source_run_id(run)
    if source_run_id is None:
        raise IssueToPrRunRejectedError(
            reason_code="replay_source_required",
            message="Replay mode requires replay_source_run_id from a captured real run.",
            http_status=422,
        )
    fixture = load_issue_to_pr_replay_fixture(source_run_id, replay_fixture_dir)
    return fixture.to_graph_state(
        run_id=run.id,
        autonomy_level=cast(Any, run.autonomy_level),
        actor_id=request.actor_id,
        trace_id=request.trace_id,
    )


async def add_planner_outputs_to_graph_state(
    planner: IssueToPrPlanner,
    graph_state: IssueToPrState,
) -> IssueToPrState:
    if not graph_state.get("evidence"):
        graph_state["evidence"] = build_evidence_from_state(graph_state)
    proposal = await planner.create_patch_plan(graph_state)
    graph_state["proposal"] = proposal.model_dump(mode="json")
    evaluation = await planner.evaluate_patch_plan(graph_state, proposal)
    graph_state["evaluation"] = evaluation.model_dump(mode="json")
    return graph_state


def build_evidence_from_state(graph_state: IssueToPrState) -> list[dict[str, Any]]:
    issue = graph_state["issue"]
    evidence: list[dict[str, Any]] = [
        {
            "kind": "github_issue",
            "title": issue["title"],
            "source_uri": issue["url"],
        }
    ]
    for file_payload in graph_state.get("context_files", []):
        evidence.append(
            {
                "kind": "github_file",
                "title": file_payload["path"],
                "source_uri": build_github_blob_uri(
                    repository=graph_state["repository"],
                    ref=file_payload["ref"],
                    path=file_payload["path"],
                ),
                "sha": file_payload["sha"],
            }
        )
    return evidence


def get_replay_source_run_id(run: WorkflowRun) -> str | None:
    payload = run.input_payload or {}
    return string_or_none(payload.get("replay_source_run_id"))


def ensure_replay_request_does_not_override_fixture(request: IssueToPrRunRequest) -> None:
    if any(
        value is not None
        for value in (
            request.repository,
            request.issue_number,
            request.issue_url,
            request.ref,
            request.context_paths,
        )
    ):
        raise IssueToPrRunRejectedError(
            reason_code="replay_input_override_not_allowed",
            message="Replay evidence collection must use the captured replay fixture inputs.",
            http_status=422,
        )


def parse_github_issue_url(issue_url: str) -> tuple[str, int]:
    parsed = urlparse(issue_url)
    if parsed.scheme not in {"http", "https"} or parsed.netloc != "github.com":
        raise IssueToPrRunRejectedError(
            reason_code="github_issue_url_invalid",
            message="GitHub issue URL must use https://github.com/{owner}/{repo}/issues/{number}.",
            http_status=422,
        )
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) != 4 or parts[2] != "issues":
        raise IssueToPrRunRejectedError(
            reason_code="github_issue_url_invalid",
            message="GitHub issue URL must use https://github.com/{owner}/{repo}/issues/{number}.",
            http_status=422,
        )
    try:
        issue_number = int(parts[3])
    except ValueError as exc:
        raise IssueToPrRunRejectedError(
            reason_code="github_issue_url_invalid",
            message="GitHub issue URL issue number must be a positive integer.",
            http_status=422,
        ) from exc
    if issue_number <= 0:
        raise IssueToPrRunRejectedError(
            reason_code="github_issue_url_invalid",
            message="GitHub issue URL issue number must be a positive integer.",
            http_status=422,
        )
    return f"{parts[0]}/{parts[1]}", issue_number


def persist_graph_evidence(
    session: Session,
    run: WorkflowRun,
    graph_state: IssueToPrState,
) -> list[EvidenceRecord]:
    issue = graph_state["issue"]
    captured_at = utc_now()
    records = [
        EvidenceRecord(
            id=uuid4(),
            run_id=run.id,
            workflow_id=run.workflow_id,
            kind="api_response",
            source_system="github",
            source_uri=str(issue["url"]),
            title=str(issue["title"]),
            content_hash=hash_mapping(issue),
            evidence_metadata={
                "evidence_kind": "github_issue",
                "labels": issue.get("labels", []),
                "author": issue.get("author"),
            },
            captured_at=captured_at,
        )
    ]
    for file_payload in graph_state.get("context_files", []):
        file_record = file_payload
        records.append(
            EvidenceRecord(
                id=uuid4(),
                run_id=run.id,
                workflow_id=run.workflow_id,
                kind="code",
                source_system="github",
                source_uri=build_github_blob_uri(
                    repository=str(graph_state["repository"]),
                    ref=str(file_record["ref"]),
                    path=str(file_record["path"]),
                ),
                title=str(file_record["path"]),
                content_hash=hash_mapping(
                    {
                        "path": file_record["path"],
                        "ref": file_record["ref"],
                        "sha": file_record["sha"],
                        "content": file_record["content"],
                    }
                ),
                evidence_metadata={
                    "evidence_kind": "github_file",
                    "path": file_record["path"],
                    "ref": file_record["ref"],
                    "sha": file_record["sha"],
                    "byte_count": len(str(file_record["content"]).encode("utf-8")),
                },
                captured_at=captured_at,
            )
        )
    for record in records:
        session.add(record)
    session.flush()
    return records


def collect_tool_policy_decision_ids(graph_state: IssueToPrState) -> list[str]:
    raw_decisions = graph_state.get("policy_decision_ids", [])
    return [decision for decision in raw_decisions if isinstance(decision, str) and decision]


def string_or_none(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def positive_int_or_none(value: object) -> int | None:
    if isinstance(value, int) and value > 0:
        return value
    return None


def string_list_or_empty(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item]


def build_github_blob_uri(repository: str, ref: str, path: str) -> str:
    clean_path = "/".join(part for part in path.split("/") if part)
    return f"https://github.com/{repository}/blob/{ref}/{clean_path}"


def hash_mapping(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256(encoded).hexdigest()
