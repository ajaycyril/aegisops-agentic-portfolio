from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from datetime import timedelta
from hashlib import sha256
from pathlib import Path
from typing import Any, Literal, Protocol, Self, cast
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.orm import Session

from aegisops_api.audit import AuditEventInput, write_audit_event
from aegisops_api.budget import BudgetPolicyEvaluator, enforce_run_budget
from aegisops_api.db.models import Approval, EvidenceRecord, WorkflowRun, utc_now
from aegisops_api.tools import ToolPolicyEvaluator
from aegisops_api.tools.adapters import ToolAdapterRegistry
from aegisops_api.tools.registry import ToolRegistry
from aegisops_api.workflows.incident_response_investigator.graph import (
    INCIDENT_WORKFLOW_ID,
    IncidentInvestigationGraphDependencies,
    IncidentInvestigationInput,
    IncidentInvestigationState,
    IncidentInvestigationToolRuntime,
    IncidentTimeWindow,
    PolicyBackedIncidentToolRuntime,
    as_incident_investigation_state,
    build_github_blob_uri,
    collect_policy_decision_ids,
    collect_tool_call_ids,
    create_incident_investigation_graph,
    evidence_auditor_node,
)
from aegisops_api.workflows.incident_response_investigator.replay import (
    load_incident_replay_fixture,
)
from aegisops_api.workflows.registry import WorkflowRegistry

IncidentRunStage = Literal["incident_evidence_collected", "incident_rca_draft_created"]
IncidentApprovalActionType = Literal["rollback", "incident_update", "paging_action"]
IncidentApprovalDecisionAction = Literal["approve", "reject"]
IncidentApprovalDecisionStatus = Literal["approved", "rejected"]


class IncidentInvestigationRejectedError(RuntimeError):
    def __init__(self, reason_code: str, message: str, http_status: int = 409) -> None:
        super().__init__(message)
        self.reason_code = reason_code
        self.message = message
        self.http_status = http_status


class IncidentInvestigationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    incident_id: str | None = Field(default=None, min_length=1)
    service: str | None = Field(default=None, min_length=1)
    time_window: IncidentTimeWindow | None = None
    severity: str | None = Field(default=None, min_length=1)
    environment: str | None = Field(default=None, min_length=1)
    repository: str | None = Field(default=None, min_length=1)
    ref: str | None = Field(default=None, min_length=1)
    suspect_paths: list[str] | None = Field(default=None, max_length=10)
    actor_id: str | None = None
    trace_id: str | None = None
    include_rca: bool = False


class IncidentEvidenceRecordSummary(BaseModel):
    id: UUID
    kind: str
    source_system: str
    source_uri: str | None
    title: str
    content_hash: str


class IncidentEvidenceGroundingCheck(BaseModel):
    evidence_kind: str
    title: str
    source_system: str
    source_uri: str | None
    grounded: bool
    reason_codes: list[str]


class IncidentEvidenceValidationSummary(BaseModel):
    grounded: bool
    evidence_count: int
    grounded_count: int
    missing_source_uri_count: int
    rejected_reason_codes: list[str]
    checks: list[IncidentEvidenceGroundingCheck]


class IncidentRcaClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim_type: Literal["timeline", "probable_cause", "impact", "next_step"]
    statement: str = Field(min_length=1)
    evidence_uris: list[str] = Field(min_length=1)


class IncidentRcaDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["incident_response_investigator.rca_draft.v1"] = (
        "incident_response_investigator.rca_draft.v1"
    )
    incident_id: str
    service: str
    title: str
    summary: str
    confidence: Literal["low", "medium", "high"]
    source_evidence_uris: list[str] = Field(min_length=1)
    claims: list[IncidentRcaClaim] = Field(min_length=1)
    approval_required_for: list[Literal["rollback", "incident_update", "paging_action"]]
    requires_human_review: Literal[True] = True
    write_actions_enabled: Literal[False] = False

    @model_validator(mode="after")
    def validate_claim_grounding(self) -> Self:
        allowed_uris = set(self.source_evidence_uris)
        for claim in self.claims:
            claim_uris = set(claim.evidence_uris)
            if not claim_uris:
                raise ValueError("RCA claims must cite at least one evidence URI.")
            if not claim_uris.issubset(allowed_uris):
                raise ValueError("RCA claims may only cite grounded source evidence URIs.")
        return self


class IncidentProposedAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_type: IncidentApprovalActionType
    summary: str = Field(min_length=1)
    rationale: str = Field(min_length=1)
    evidence_uris: list[str] = Field(min_length=1)
    proposed_payload_metadata: dict[str, Any] = Field(default_factory=dict)


class IncidentApprovalReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rca_draft: IncidentRcaDraft
    proposed_actions: list[IncidentProposedAction] = Field(min_length=1, max_length=3)
    requested_by: str = Field(default="agent-runtime", min_length=1)
    actor_id: str | None = None
    trace_id: str | None = None

    @model_validator(mode="after")
    def validate_action_evidence_is_grounded(self) -> Self:
        allowed_uris = set(self.rca_draft.source_evidence_uris)
        for action in self.proposed_actions:
            if not set(action.evidence_uris).issubset(allowed_uris):
                raise ValueError("Incident approval actions may only cite RCA evidence URIs.")
        return self


class IncidentApprovalReviewItem(BaseModel):
    id: UUID
    status: str
    requested_action: IncidentApprovalActionType
    risk_class: str
    requested_by: str
    requested_at: str
    expires_at: str


class IncidentApprovalReviewResponse(BaseModel):
    run_id: UUID
    workflow_id: str
    run_status: str
    approval_state: Literal["pending_human_review"] = "pending_human_review"
    approvals: list[IncidentApprovalReviewItem]
    write_actions_enabled: Literal[False] = False
    external_actions_enabled: Literal[False] = False


class IncidentApprovalDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: IncidentApprovalDecisionAction
    approver_id: str = Field(min_length=1)
    decision_reason: str = Field(min_length=1)
    actor_id: str | None = None
    trace_id: str | None = None


class IncidentApprovalPolicyDecisionSummary(BaseModel):
    allowed: bool
    requires_approval: bool
    decision_id: str | None
    reason_codes: list[str]


class IncidentApprovalDecisionResponse(BaseModel):
    approval_id: UUID
    run_id: UUID
    workflow_id: str
    run_status: str
    requested_action: IncidentApprovalActionType
    approval_status: IncidentApprovalDecisionStatus
    approver_id: str
    decided_at: str
    policy_decision: IncidentApprovalPolicyDecisionSummary
    write_actions_enabled: Literal[False] = False
    external_actions_enabled: Literal[False] = False


class IncidentApprovalPolicyEvaluator(Protocol):
    async def evaluate(self, input_payload: dict[str, Any]) -> Any:
        pass


class IncidentInvestigationResponse(BaseModel):
    run_id: UUID
    workflow_id: str
    run_status: str
    stage: IncidentRunStage
    incident_id: str
    service: str
    log_event_count: int
    deployment_event_count: int
    code_file_count: int
    tool_call_ids: list[str]
    evidence_records: list[IncidentEvidenceRecordSummary]
    policy_decision_ids: list[str]
    evidence_validation: IncidentEvidenceValidationSummary
    rca_draft_created: bool = False
    rca_draft: IncidentRcaDraft | None = None
    rca_generation_enabled: Literal[False] = False
    write_actions_enabled: Literal[False] = False


async def collect_incident_evidence(
    run_id: UUID,
    request: IncidentInvestigationRequest,
    session: Session,
    workflow_registry: WorkflowRegistry,
    tool_registry: ToolRegistry,
    policy_evaluator: ToolPolicyEvaluator,
    adapter_registry: ToolAdapterRegistry,
    available_connectors: set[str],
    tool_runtime: IncidentInvestigationToolRuntime | None = None,
    replay_fixture_dir: Path | None = None,
    budget_evaluator: BudgetPolicyEvaluator | None = None,
) -> IncidentInvestigationResponse:
    run = session.get(WorkflowRun, run_id)
    if run is None:
        raise IncidentInvestigationRejectedError(
            reason_code="workflow_run_not_found",
            message="Workflow run was not found.",
            http_status=404,
        )
    ensure_run_can_collect_incident_evidence(run)
    await enforce_run_budget(
        run=run,
        session=session,
        budget_evaluator=budget_evaluator,
        action="workflow_graph.collect_incident_evidence",
        actor_id=request.actor_id,
        trace_id=request.trace_id,
    )

    graph_state: IncidentInvestigationState | None = None
    graph_input: IncidentInvestigationInput | None = None
    rca_draft: IncidentRcaDraft | None = None
    try:
        run.status = "running"
        if run.execution_mode == "replay":
            ensure_replay_request_does_not_override_fixture(request)
            graph_state = load_replay_graph_state(run, request, replay_fixture_dir)
            start_payload = {
                "stage": "incident_evidence_collection",
                "execution_mode": "replay",
                "replay_source_run_id": get_replay_source_run_id(run),
                "incident_id": graph_state["incident_id"],
                "service": graph_state["service"],
                "suspect_path_count": len(graph_state.get("suspect_paths", [])),
                "rca_generation_enabled": False,
                "write_actions_enabled": False,
            }
        else:
            graph_input = build_graph_input_from_run(run, request)
            start_payload = {
                "stage": "incident_evidence_collection",
                "execution_mode": "live",
                "incident_id": graph_input.incident_id,
                "service": graph_input.service,
                "suspect_path_count": len(graph_input.suspect_paths),
                "rca_generation_enabled": False,
                "write_actions_enabled": False,
            }
        write_audit_event(
            session,
            AuditEventInput(
                run_id=run.id,
                workflow_id=run.workflow_id,
                event_type="workflow_graph.started",
                actor_type="user" if request.actor_id else "system",
                actor_id=request.actor_id,
                action="workflow_graph.collect_incident_evidence",
                resource_type="workflow_run",
                resource_id=str(run.id),
                trace_id=request.trace_id,
                payload=start_payload,
            ),
        )
        session.flush()
        if graph_state is None:
            if graph_input is None:
                raise IncidentInvestigationRejectedError(
                    reason_code="workflow_graph_not_initialized",
                    message="Workflow graph was not initialized.",
                )
            runtime = tool_runtime or PolicyBackedIncidentToolRuntime(
                workflow_registry=workflow_registry,
                tool_registry=tool_registry,
                session=session,
                policy_evaluator=policy_evaluator,
                adapter_registry=adapter_registry,
                available_connectors=available_connectors,
                budget_evaluator=budget_evaluator,
            )
            graph = create_incident_investigation_graph(
                IncidentInvestigationGraphDependencies(tool_runtime=runtime)
            )
            graph_state = as_incident_investigation_state(
                await graph.ainvoke(graph_input.to_initial_state())
            )
        elif not graph_state.get("evidence"):
            graph_state.update(evidence_auditor_node(graph_state))
        evidence_validation = validate_incident_evidence_grounding(graph_state)
        if request.include_rca:
            ensure_evidence_is_grounded_for_rca(evidence_validation)
            rca_draft = build_incident_rca_draft(graph_state, evidence_validation)
        evidence_records = persist_incident_evidence(session, run, graph_state)
        if rca_draft is not None:
            evidence_records.append(persist_incident_rca_draft(session, run, rca_draft))
        policy_decision_ids = collect_policy_decision_ids(graph_state)
        write_audit_event(
            session,
            AuditEventInput(
                run_id=run.id,
                workflow_id=run.workflow_id,
                event_type=(
                    "workflow_graph.rca_draft_created"
                    if rca_draft is not None
                    else "workflow_graph.evidence_collected"
                ),
                actor_type="user" if request.actor_id else "system",
                actor_id=request.actor_id,
                action="workflow_graph.collect_incident_evidence",
                resource_type="workflow_run",
                resource_id=str(run.id),
                trace_id=request.trace_id,
                payload={
                    "stage": (
                        "incident_rca_draft_created"
                        if rca_draft is not None
                        else "incident_evidence_collected"
                    ),
                    "evidence_count": len(evidence_records),
                    "tool_call_count": len(collect_tool_call_ids(graph_state)),
                    "policy_decision_ids": policy_decision_ids,
                    "evidence_validation": evidence_validation.model_dump(mode="json"),
                    "rca_draft_created": rca_draft is not None,
                    "rca_generation_enabled": False,
                    "write_actions_enabled": False,
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
                action="workflow_graph.collect_incident_evidence",
                resource_type="workflow_run",
                resource_id=str(run.id),
                trace_id=request.trace_id,
                payload={
                    "stage": "incident_evidence_collection",
                    "error_type": type(exc).__name__,
                },
            ),
        )
        session.commit()
        raise

    return IncidentInvestigationResponse(
        run_id=run.id,
        workflow_id=run.workflow_id,
        run_status=run.status,
        stage=(
            "incident_rca_draft_created"
            if rca_draft is not None
            else "incident_evidence_collected"
        ),
        incident_id=graph_state["incident_id"],
        service=graph_state["service"],
        log_event_count=len(graph_state.get("log_events", [])),
        deployment_event_count=len(graph_state.get("deployment_events", [])),
        code_file_count=len(graph_state.get("code_files", [])),
        tool_call_ids=collect_tool_call_ids(graph_state),
        evidence_records=[
            IncidentEvidenceRecordSummary(
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
        evidence_validation=evidence_validation,
        rca_draft_created=rca_draft is not None,
        rca_draft=rca_draft,
    )


async def decide_incident_approval(
    run_id: UUID,
    approval_id: UUID,
    request: IncidentApprovalDecisionRequest,
    session: Session,
    policy_evaluator: IncidentApprovalPolicyEvaluator,
) -> IncidentApprovalDecisionResponse:
    approval = session.get(Approval, approval_id)
    if approval is None:
        raise IncidentInvestigationRejectedError(
            reason_code="approval_not_found",
            message="Approval record was not found.",
            http_status=404,
        )
    if approval.run_id != run_id:
        raise IncidentInvestigationRejectedError(
            reason_code="approval_run_mismatch",
            message="Approval record does not belong to this workflow run.",
        )
    run = session.get(WorkflowRun, run_id)
    if run is None:
        raise IncidentInvestigationRejectedError(
            reason_code="workflow_run_not_found",
            message="Workflow run was not found.",
            http_status=404,
        )
    ensure_incident_approval_can_be_decided(run, approval)

    policy_input = build_incident_approval_decision_policy_input(
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
                    "external_actions_enabled": False,
                },
            ),
        )
        session.commit()
        raise IncidentInvestigationRejectedError(
            reason_code="approval_decision_policy_denied",
            message="OPA policy denied the incident approval decision.",
            http_status=403,
        )

    decided_at = utc_now()
    approval.status = "approved" if request.decision == "approve" else "rejected"
    approval.approver_id = request.approver_id
    approval.policy_decision_id = decision.decision_id
    approval.decided_at = decided_at
    approval.decision_payload = {
        "schema_version": "incident_response_investigator.approval_decision.v1",
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
        "external_actions_enabled": False,
    }
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
                "external_actions_enabled": False,
            },
        ),
    )
    session.commit()

    return IncidentApprovalDecisionResponse(
        approval_id=approval.id,
        run_id=run.id,
        workflow_id=run.workflow_id,
        run_status=run.status,
        requested_action=cast(IncidentApprovalActionType, approval.requested_action),
        approval_status=cast(IncidentApprovalDecisionStatus, approval.status),
        approver_id=request.approver_id,
        decided_at=decided_at.isoformat(),
        policy_decision=IncidentApprovalPolicyDecisionSummary(
            allowed=decision.allowed,
            requires_approval=decision.requires_approval,
            decision_id=decision.decision_id,
            reason_codes=decision.reason_codes,
        ),
    )


async def request_incident_approval_review(
    run_id: UUID,
    request: IncidentApprovalReviewRequest,
    session: Session,
) -> IncidentApprovalReviewResponse:
    run = session.get(WorkflowRun, run_id)
    if run is None:
        raise IncidentInvestigationRejectedError(
            reason_code="workflow_run_not_found",
            message="Workflow run was not found.",
            http_status=404,
        )
    ensure_run_can_request_incident_approval(run)

    requested_at = utc_now()
    expires_at = requested_at + timedelta(hours=24)
    approvals: list[Approval] = []
    try:
        run.status = "waiting_for_approval"
        for action in request.proposed_actions:
            risk_class = incident_action_risk_class(action.action_type)
            approval = Approval(
                id=uuid4(),
                run_id=run.id,
                status="pending",
                risk_class=risk_class,
                requested_action=action.action_type,
                requested_by=request.requested_by,
                request_payload={
                    "schema_version": "incident_response_investigator.approval_review.v1",
                    "rca_draft": request.rca_draft.model_dump(mode="json"),
                    "proposed_action": action.model_dump(mode="json"),
                    "approval_contract": {
                        "approval_table": "approvals",
                        "write_actions_enabled": False,
                        "external_actions_enabled": False,
                        "dry_run_only": True,
                        "future_tool_call_approval_id_required": True,
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
                        "risk_class": risk_class,
                        "requested_by": request.requested_by,
                        "write_actions_enabled": False,
                        "external_actions_enabled": False,
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
                action="workflow_run.request_incident_action_approval",
                resource_type="workflow_run",
                resource_id=str(run.id),
                trace_id=request.trace_id,
                payload={
                    "approval_count": len(approvals),
                    "requested_actions": [approval.requested_action for approval in approvals],
                    "write_actions_enabled": False,
                    "external_actions_enabled": False,
                },
            ),
        )
        session.commit()
    except Exception:
        session.rollback()
        raise

    return IncidentApprovalReviewResponse(
        run_id=run.id,
        workflow_id=run.workflow_id,
        run_status=run.status,
        approvals=[
            IncidentApprovalReviewItem(
                id=approval.id,
                status=approval.status,
                requested_action=cast(IncidentApprovalActionType, approval.requested_action),
                risk_class=approval.risk_class,
                requested_by=approval.requested_by,
                requested_at=approval.requested_at.isoformat(),
                expires_at=expires_at.isoformat(),
            )
            for approval in approvals
        ],
    )


def ensure_run_can_collect_incident_evidence(run: WorkflowRun) -> None:
    if run.workflow_id != INCIDENT_WORKFLOW_ID:
        raise IncidentInvestigationRejectedError(
            reason_code="workflow_not_supported",
            message="This runtime path only supports incident_response_investigator runs.",
        )
    if run.status not in {"queued", "running"}:
        raise IncidentInvestigationRejectedError(
            reason_code="workflow_run_not_executable",
            message=f"Workflow run status is {run.status}.",
        )
    if run.execution_mode != "live":
        if run.execution_mode == "replay":
            if get_replay_source_run_id(run) is None:
                raise IncidentInvestigationRejectedError(
                    reason_code="replay_source_required",
                    message="Replay mode requires replay_source_run_id from a captured real run.",
                    http_status=422,
                )
            return
        raise IncidentInvestigationRejectedError(
            reason_code="execution_mode_not_supported",
            message=f"Workflow run execution mode is {run.execution_mode}.",
        )


def ensure_run_can_request_incident_approval(run: WorkflowRun) -> None:
    if run.workflow_id != INCIDENT_WORKFLOW_ID:
        raise IncidentInvestigationRejectedError(
            reason_code="workflow_not_supported",
            message="This runtime path only supports incident_response_investigator runs.",
        )
    if run.status not in {"running", "waiting_for_approval"}:
        raise IncidentInvestigationRejectedError(
            reason_code="workflow_run_not_ready_for_approval",
            message=f"Workflow run status is {run.status}.",
        )


def ensure_incident_approval_can_be_decided(run: WorkflowRun, approval: Approval) -> None:
    if run.workflow_id != INCIDENT_WORKFLOW_ID:
        raise IncidentInvestigationRejectedError(
            reason_code="workflow_not_supported",
            message="This runtime path only supports incident_response_investigator runs.",
        )
    if run.status != "waiting_for_approval":
        raise IncidentInvestigationRejectedError(
            reason_code="workflow_run_not_waiting_for_approval",
            message=f"Workflow run status is {run.status}.",
        )
    if approval.status != "pending":
        raise IncidentInvestigationRejectedError(
            reason_code="approval_not_pending",
            message=f"Approval status is {approval.status}.",
        )
    if approval.requested_action not in {"rollback", "paging_action", "incident_update"}:
        raise IncidentInvestigationRejectedError(
            reason_code="approval_action_not_supported",
            message=f"Approval action is {approval.requested_action}.",
        )
    if approval.request_payload.get("schema_version") != (
        "incident_response_investigator.approval_review.v1"
    ):
        raise IncidentInvestigationRejectedError(
            reason_code="approval_payload_invalid",
            message="Approval payload is not an Incident approval-review record.",
        )


def build_incident_approval_decision_policy_input(
    run: WorkflowRun,
    approval: Approval,
    request: IncidentApprovalDecisionRequest,
) -> dict[str, Any]:
    return {
        "workflow_id": run.workflow_id,
        "autonomy_level": run.autonomy_level,
        "decision_action": request.decision,
        "risk_class": approval.risk_class,
        "requested_action": approval.requested_action,
        "approver_id": request.approver_id,
        "approval": {
            "status": approval.status,
            "requested_by": approval.requested_by,
            "write_actions_enabled": extract_incident_write_actions_enabled(
                approval.request_payload
            ),
            "request_payload": approval.request_payload,
        },
    }


def extract_incident_write_actions_enabled(request_payload: dict[str, Any]) -> bool:
    approval_contract = request_payload.get("approval_contract", {})
    if not isinstance(approval_contract, dict):
        return True
    return bool(approval_contract.get("write_actions_enabled", True))


def incident_action_risk_class(action_type: IncidentApprovalActionType) -> str:
    if action_type == "rollback":
        return "write"
    return "external_message"


def build_graph_input_from_run(
    run: WorkflowRun,
    request: IncidentInvestigationRequest,
) -> IncidentInvestigationInput:
    payload = run.input_payload or {}
    incident_id = request.incident_id or string_or_none(payload.get("incident_id"))
    service = request.service or string_or_none(payload.get("service"))
    time_window = request.time_window or time_window_or_none(payload.get("time_window"))
    if incident_id is None or service is None or time_window is None:
        raise IncidentInvestigationRejectedError(
            reason_code="incident_input_missing",
            message="Provide incident_id, service, and time_window.",
            http_status=422,
        )
    return IncidentInvestigationInput(
        run_id=run.id,
        incident_id=incident_id,
        service=service,
        time_window=time_window,
        severity=request.severity or string_or_none(payload.get("severity")),
        environment=request.environment or string_or_none(payload.get("environment")),
        repository=request.repository or string_or_none(payload.get("repository")),
        ref=request.ref or string_or_none(payload.get("ref")) or "main",
        suspect_paths=(
            request.suspect_paths
            if request.suspect_paths is not None
            else string_list_or_empty(payload.get("suspect_paths"))
        ),
        autonomy_level=cast(Any, run.autonomy_level),
        actor_id=request.actor_id or string_or_none(payload.get("actor_id")),
        trace_id=request.trace_id or string_or_none(payload.get("trace_id")),
    )


def load_replay_graph_state(
    run: WorkflowRun,
    request: IncidentInvestigationRequest,
    replay_fixture_dir: Path | None,
) -> IncidentInvestigationState:
    source_run_id = get_replay_source_run_id(run)
    if source_run_id is None:
        raise IncidentInvestigationRejectedError(
            reason_code="replay_source_required",
            message="Replay mode requires replay_source_run_id from a captured real run.",
            http_status=422,
        )
    fixture = load_incident_replay_fixture(source_run_id, replay_fixture_dir)
    return fixture.to_graph_state(
        run_id=run.id,
        autonomy_level=cast(Any, run.autonomy_level),
        actor_id=request.actor_id,
        trace_id=request.trace_id,
    )


def get_replay_source_run_id(run: WorkflowRun) -> str | None:
    payload = run.input_payload or {}
    return string_or_none(payload.get("replay_source_run_id"))


def ensure_replay_request_does_not_override_fixture(
    request: IncidentInvestigationRequest,
) -> None:
    if any(
        value is not None
        for value in (
            request.incident_id,
            request.service,
            request.time_window,
            request.severity,
            request.environment,
            request.repository,
            request.ref,
            request.suspect_paths,
        )
    ):
        raise IncidentInvestigationRejectedError(
            reason_code="replay_input_override_not_allowed",
            message="Replay evidence collection must use the captured replay fixture inputs.",
            http_status=422,
        )


def validate_incident_evidence_grounding(
    graph_state: IncidentInvestigationState,
) -> IncidentEvidenceValidationSummary:
    checks = [
        validate_single_evidence_grounding(evidence)
        for evidence in graph_state.get("evidence", [])
    ]
    rejected_reason_codes = ordered_unique(
        reason_code for check in checks for reason_code in check.reason_codes
    )
    if not checks:
        rejected_reason_codes = ["evidence_missing"]

    return IncidentEvidenceValidationSummary(
        grounded=bool(checks) and all(check.grounded for check in checks),
        evidence_count=len(checks),
        grounded_count=sum(1 for check in checks if check.grounded),
        missing_source_uri_count=sum(1 for check in checks if check.source_uri is None),
        rejected_reason_codes=rejected_reason_codes,
        checks=checks,
    )


def validate_single_evidence_grounding(
    evidence: Mapping[str, Any],
) -> IncidentEvidenceGroundingCheck:
    evidence_kind = str(evidence.get("kind") or "unknown")
    source_system = str(evidence.get("source_system") or "unknown")
    source_uri = string_or_none(evidence.get("source_uri"))
    payload = mapping_or_empty(evidence.get("payload"))
    reason_codes: list[str] = []

    if source_uri is None:
        reason_codes.append("source_uri_missing")
    if not payload:
        reason_codes.append("payload_missing")

    for required_field in required_grounding_fields(evidence_kind):
        if not string_or_none(payload.get(required_field)):
            reason_codes.append(f"required_field_missing:{required_field}")

    if evidence_kind == "unknown":
        reason_codes.append("evidence_kind_unknown")

    return IncidentEvidenceGroundingCheck(
        evidence_kind=evidence_kind,
        title=str(evidence.get("title") or evidence_kind),
        source_system=source_system,
        source_uri=source_uri,
        grounded=not reason_codes,
        reason_codes=reason_codes,
    )


def required_grounding_fields(evidence_kind: str) -> tuple[str, ...]:
    if evidence_kind == "observability_log_event":
        return ("event_id", "timestamp")
    if evidence_kind == "deployment_event":
        return ("deployment_id", "deployed_at")
    if evidence_kind == "github_file":
        return ("path", "ref", "sha")
    return ()


def ensure_evidence_is_grounded_for_rca(
    validation: IncidentEvidenceValidationSummary,
) -> None:
    if validation.grounded:
        return
    raise IncidentInvestigationRejectedError(
        reason_code="incident_evidence_not_grounded",
        message=(
            "RCA draft creation requires every evidence record to include source URIs "
            "and kind-specific grounding fields."
        ),
        http_status=422,
    )


def build_incident_rca_draft(
    graph_state: IncidentInvestigationState,
    validation: IncidentEvidenceValidationSummary,
) -> IncidentRcaDraft:
    source_evidence_uris = [
        check.source_uri for check in validation.checks if check.grounded and check.source_uri
    ]
    claims: list[IncidentRcaClaim] = [
        *timeline_claims_from_deployments(graph_state, source_evidence_uris),
        *timeline_claims_from_logs(graph_state, source_evidence_uris),
        *timeline_claims_from_code(graph_state, source_evidence_uris),
    ]
    claims.extend(probable_cause_claims(graph_state, source_evidence_uris))
    claims.append(
        IncidentRcaClaim(
            claim_type="next_step",
            statement=(
                "Human incident owner must review the cited evidence before approving "
                "rollback, paging, or customer-visible incident updates."
            ),
            evidence_uris=source_evidence_uris[: min(3, len(source_evidence_uris))],
        )
    )

    return IncidentRcaDraft(
        incident_id=graph_state["incident_id"],
        service=graph_state["service"],
        title=f"RCA draft: {graph_state['incident_id']} / {graph_state['service']}",
        summary=(
            f"Draft RCA contract for {graph_state['incident_id']} with "
            f"{len(source_evidence_uris)} grounded evidence source"
            f"{'' if len(source_evidence_uris) == 1 else 's'}. "
            "This is not an approved production action."
        ),
        confidence="medium" if len(source_evidence_uris) >= 2 else "low",
        source_evidence_uris=source_evidence_uris,
        claims=claims,
        approval_required_for=["rollback", "incident_update", "paging_action"],
    )


def timeline_claims_from_deployments(
    graph_state: IncidentInvestigationState,
    allowed_uris: list[str],
) -> list[IncidentRcaClaim]:
    claims: list[IncidentRcaClaim] = []
    for deployment in graph_state.get("deployment_events", [])[:3]:
        uri = string_or_none(deployment.get("source_uri"))
        if uri not in allowed_uris:
            continue
        descriptor = (
            string_or_none(deployment.get("deployment_id"))
            or string_or_none(deployment.get("version"))
            or string_or_none(deployment.get("commit_sha"))
            or "deployment event"
        )
        deployed_at = string_or_none(deployment.get("deployed_at")) or "the incident window"
        claims.append(
            IncidentRcaClaim(
                claim_type="timeline",
                statement=(
                    f"Deployment {descriptor} was recorded for "
                    f"{graph_state['service']} at {deployed_at}."
                ),
                evidence_uris=[uri],
            )
        )
    return claims


def timeline_claims_from_logs(
    graph_state: IncidentInvestigationState,
    allowed_uris: list[str],
) -> list[IncidentRcaClaim]:
    claims: list[IncidentRcaClaim] = []
    for event in graph_state.get("log_events", [])[:3]:
        uri = string_or_none(event.get("source_uri"))
        if uri not in allowed_uris:
            continue
        event_id = string_or_none(event.get("event_id")) or "log event"
        severity = string_or_none(event.get("severity")) or "unclassified"
        timestamp = string_or_none(event.get("timestamp")) or "the incident window"
        claims.append(
            IncidentRcaClaim(
                claim_type="impact",
                statement=(
                    f"Log event {event_id} recorded {severity} severity for "
                    f"{graph_state['service']} at {timestamp}."
                ),
                evidence_uris=[uri],
            )
        )
    return claims


def timeline_claims_from_code(
    graph_state: IncidentInvestigationState,
    allowed_uris: list[str],
) -> list[IncidentRcaClaim]:
    claims: list[IncidentRcaClaim] = []
    repository = graph_state.get("repository")
    for file_payload in graph_state.get("code_files", [])[:3]:
        if repository is None:
            continue
        uri = build_github_blob_uri(
            repository=repository,
            ref=str(file_payload["ref"]),
            path=str(file_payload["path"]),
        )
        if uri not in allowed_uris:
            continue
        claims.append(
            IncidentRcaClaim(
                claim_type="timeline",
                statement=(
                    f"Repository file {file_payload['path']} at ref {file_payload['ref']} "
                    "was included as suspect code evidence."
                ),
                evidence_uris=[uri],
            )
        )
    return claims


def probable_cause_claims(
    graph_state: IncidentInvestigationState,
    allowed_uris: list[str],
) -> list[IncidentRcaClaim]:
    log_uris = [
        uri
        for event in graph_state.get("log_events", [])
        if (uri := string_or_none(event.get("source_uri"))) in allowed_uris
    ]
    deployment_uris = [
        uri
        for deployment in graph_state.get("deployment_events", [])
        if (uri := string_or_none(deployment.get("source_uri"))) in allowed_uris
    ]
    code_uris = [
        build_github_blob_uri(
            repository=str(graph_state["repository"]),
            ref=str(file_payload["ref"]),
            path=str(file_payload["path"]),
        )
        for file_payload in graph_state.get("code_files", [])
        if graph_state.get("repository") is not None
    ]
    code_uris = [uri for uri in code_uris if uri in allowed_uris]

    claims: list[IncidentRcaClaim] = []
    if log_uris and deployment_uris:
        claims.append(
            IncidentRcaClaim(
                claim_type="probable_cause",
                statement=(
                    "A deployment event and incident-window service errors are both present; "
                    "the deployed change is a grounded investigation lead, not an approved "
                    "root cause."
                ),
                evidence_uris=[deployment_uris[0], log_uris[0]],
            )
        )
    if code_uris:
        claims.append(
            IncidentRcaClaim(
                claim_type="probable_cause",
                statement=(
                    "Suspect code evidence was captured for reviewer inspection before any "
                    "remediation or rollback is proposed."
                ),
                evidence_uris=[code_uris[0]],
            )
        )
    return claims


def persist_incident_evidence(
    session: Session,
    run: WorkflowRun,
    graph_state: IncidentInvestigationState,
) -> list[EvidenceRecord]:
    captured_at = utc_now()
    records: list[EvidenceRecord] = []
    for evidence in graph_state.get("evidence", []):
        payload = mapping_or_empty(evidence.get("payload"))
        evidence_kind = str(evidence["kind"])
        records.append(
            EvidenceRecord(
                id=uuid4(),
                run_id=run.id,
                workflow_id=run.workflow_id,
                kind=evidence_record_kind(evidence_kind),
                source_system=str(evidence["source_system"]),
                source_uri=string_or_none(evidence.get("source_uri")),
                title=str(evidence["title"]),
                content_hash=hash_mapping(payload),
                evidence_metadata=metadata_for_evidence(evidence_kind, payload),
                captured_at=captured_at,
            )
        )
    for record in records:
        session.add(record)
    session.flush()
    return records


def persist_incident_rca_draft(
    session: Session,
    run: WorkflowRun,
    rca_draft: IncidentRcaDraft,
) -> EvidenceRecord:
    payload = rca_draft.model_dump(mode="json")
    record = EvidenceRecord(
        id=uuid4(),
        run_id=run.id,
        workflow_id=run.workflow_id,
        kind="document",
        source_system="aegisops",
        source_uri=f"aegisops://workflow-runs/{run.id}/incident-rca-draft",
        title=rca_draft.title,
        content_hash=hash_mapping(payload),
        evidence_metadata={
            "schema_version": rca_draft.schema_version,
            "incident_id": rca_draft.incident_id,
            "service": rca_draft.service,
            "claim_count": len(rca_draft.claims),
            "source_evidence_uris": rca_draft.source_evidence_uris,
            "requires_human_review": rca_draft.requires_human_review,
            "write_actions_enabled": rca_draft.write_actions_enabled,
        },
        captured_at=utc_now(),
    )
    session.add(record)
    session.flush()
    return record


def evidence_record_kind(evidence_kind: str) -> str:
    if evidence_kind == "observability_log_event":
        return "log"
    if evidence_kind == "deployment_event":
        return "api_response"
    if evidence_kind == "github_file":
        return "code"
    return "api_response"


def metadata_for_evidence(evidence_kind: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    if evidence_kind == "observability_log_event":
        metadata = copy_selected_metadata(
            payload,
            ("event_id", "timestamp", "severity", "service", "trace_id", "source_uri"),
        )
        metadata["evidence_kind"] = evidence_kind
        return metadata
    if evidence_kind == "deployment_event":
        metadata = copy_selected_metadata(
            payload,
            (
                "deployment_id",
                "environment",
                "deployed_at",
                "status",
                "version",
                "commit_sha",
                "source_uri",
            ),
        )
        metadata["evidence_kind"] = evidence_kind
        return metadata
    if evidence_kind == "github_file":
        metadata = copy_selected_metadata(payload, ("path", "ref", "sha"))
        content = payload.get("content")
        if isinstance(content, str):
            metadata["byte_count"] = len(content.encode("utf-8"))
        metadata["evidence_kind"] = evidence_kind
        return metadata
    return {}


def copy_selected_metadata(payload: Mapping[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
    return {key: payload[key] for key in keys if key in payload}


def time_window_or_none(value: object) -> IncidentTimeWindow | None:
    if not isinstance(value, dict):
        return None
    return IncidentTimeWindow.model_validate(value)


def mapping_or_empty(value: object) -> Mapping[str, Any]:
    return cast(Mapping[str, Any], value) if isinstance(value, dict) else {}


def string_or_none(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def string_list_or_empty(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item]


def ordered_unique(values: Iterable[object]) -> list[str]:
    seen: set[str] = set()
    unique_values: list[str] = []
    for value in values:
        if not isinstance(value, str) or value in seen:
            continue
        seen.add(value)
        unique_values.append(value)
    return unique_values


def hash_mapping(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256(encoded).hexdigest()
