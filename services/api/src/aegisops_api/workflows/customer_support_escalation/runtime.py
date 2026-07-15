from __future__ import annotations

import json
from datetime import timedelta
from hashlib import sha256
from typing import Any, Literal, Protocol, cast
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.orm import Session

from aegisops_api.audit import AuditEventInput, write_audit_event
from aegisops_api.db.models import Approval, EvidenceRecord, WorkflowRun, utc_now
from aegisops_api.tools import ToolPolicyEvaluator
from aegisops_api.tools.adapters import ToolAdapterRegistry
from aegisops_api.tools.registry import ToolRegistry
from aegisops_api.workflows.customer_support_escalation.graph import (
    CUSTOMER_SUPPORT_WORKFLOW_ID,
    PolicyBackedSupportToolRuntime,
    SupportEscalationGraphDependencies,
    SupportEscalationInput,
    SupportEscalationState,
    SupportEscalationToolRuntime,
    as_support_escalation_state,
    collect_policy_decision_ids,
    collect_tool_call_ids,
    create_customer_support_escalation_graph,
    string_or_none,
)
from aegisops_api.workflows.registry import AutonomyLevel, WorkflowRegistry

SupportRunStage = Literal["support_context_collected", "support_response_draft_created"]
SupportApprovalDecisionAction = Literal["approve", "reject"]
SupportApprovalDecisionStatus = Literal["approved", "rejected"]


class SupportEscalationRejectedError(RuntimeError):
    def __init__(self, reason_code: str, message: str, http_status: int = 409) -> None:
        super().__init__(message)
        self.reason_code = reason_code
        self.message = message
        self.http_status = http_status


class SupportEscalationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticket_id: str | None = Field(default=None, min_length=1)
    locale: str | None = Field(default=None, min_length=1)
    actor_id: str | None = None
    trace_id: str | None = None
    include_draft: bool = False


class SupportDraftCitation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    source_uri: str = Field(min_length=1)


class SupportResponseDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["customer_support_escalation.response_draft.v1"] = (
        "customer_support_escalation.response_draft.v1"
    )
    ticket_id: str
    customer_id: str | None
    subject: str
    response_body: str = Field(min_length=1)
    citation_uris: list[str] = Field(min_length=1)
    cited_documents: list[SupportDraftCitation] = Field(min_length=1)
    requires_human_review: Literal[True] = True
    customer_message_enabled: Literal[False] = False
    external_actions_enabled: Literal[False] = False

    @model_validator(mode="after")
    def validate_citations(self) -> SupportResponseDraft:
        allowed_uris = set(self.citation_uris)
        for citation in self.cited_documents:
            if citation.source_uri not in allowed_uris:
                raise ValueError("Support draft citations must be listed in citation_uris.")
        return self


class SupportEvidenceRecordSummary(BaseModel):
    id: UUID
    kind: str
    source_system: str
    source_uri: str | None
    title: str
    content_hash: str


class SupportEscalationResponse(BaseModel):
    run_id: UUID
    workflow_id: str
    run_status: str
    stage: SupportRunStage
    ticket_id: str
    customer_id: str | None
    knowledge_document_count: int
    tool_call_ids: list[str]
    policy_decision_ids: list[str]
    evidence_records: list[SupportEvidenceRecordSummary]
    response_draft_created: bool = False
    response_draft: SupportResponseDraft | None = None
    model_response_drafting_enabled: Literal[False] = False
    customer_message_enabled: Literal[False] = False
    write_actions_enabled: Literal[False] = False


class SupportApprovalReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    response_draft: SupportResponseDraft
    requested_by: str = Field(default="agent-runtime", min_length=1)
    actor_id: str | None = None
    trace_id: str | None = None


class SupportApprovalReviewItem(BaseModel):
    id: UUID
    status: str
    requested_action: Literal["customer_message"]
    risk_class: Literal["external_message"]
    requested_by: str
    requested_at: str
    expires_at: str


class SupportApprovalReviewResponse(BaseModel):
    run_id: UUID
    workflow_id: str
    run_status: str
    approval_state: Literal["pending_human_review"] = "pending_human_review"
    approvals: list[SupportApprovalReviewItem]
    customer_message_enabled: Literal[False] = False
    external_actions_enabled: Literal[False] = False


class SupportApprovalDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: SupportApprovalDecisionAction
    approver_id: str = Field(min_length=1)
    decision_reason: str = Field(min_length=1)
    actor_id: str | None = None
    trace_id: str | None = None


class SupportApprovalPolicyDecisionSummary(BaseModel):
    allowed: bool
    requires_approval: bool
    decision_id: str | None
    reason_codes: list[str]


class SupportApprovalDecisionResponse(BaseModel):
    approval_id: UUID
    run_id: UUID
    workflow_id: str
    run_status: str
    requested_action: Literal["customer_message"]
    approval_status: SupportApprovalDecisionStatus
    approver_id: str
    decided_at: str
    policy_decision: SupportApprovalPolicyDecisionSummary
    customer_message_enabled: Literal[False] = False
    external_actions_enabled: Literal[False] = False


class SupportApprovalPolicyEvaluator(Protocol):
    async def evaluate(self, input_payload: dict[str, Any]) -> Any:
        pass


async def collect_support_escalation_context(
    run_id: UUID,
    request: SupportEscalationRequest,
    session: Session,
    workflow_registry: WorkflowRegistry,
    tool_registry: ToolRegistry,
    policy_evaluator: ToolPolicyEvaluator,
    adapter_registry: ToolAdapterRegistry,
    available_connectors: set[str],
    tool_runtime: SupportEscalationToolRuntime | None = None,
) -> SupportEscalationResponse:
    run = session.get(WorkflowRun, run_id)
    if run is None:
        raise SupportEscalationRejectedError(
            reason_code="workflow_run_not_found",
            message="Workflow run was not found.",
            http_status=404,
        )
    ensure_run_can_collect_support_context(run)
    graph_input = build_graph_input_from_run(run, request)

    try:
        run.status = "running"
        write_audit_event(
            session,
            AuditEventInput(
                run_id=run.id,
                workflow_id=run.workflow_id,
                event_type="workflow_graph.started",
                actor_type="user" if request.actor_id else "system",
                actor_id=request.actor_id,
                action="workflow_graph.collect_support_context",
                resource_type="workflow_run",
                resource_id=str(run.id),
                trace_id=request.trace_id,
                payload={
                    "stage": "support_context_collection",
                    "ticket_id": graph_input.ticket_id,
                    "response_drafting_enabled": False,
                    "customer_message_enabled": False,
                    "write_actions_enabled": False,
                },
            ),
        )
        session.flush()
        runtime = tool_runtime or PolicyBackedSupportToolRuntime(
            workflow_registry=workflow_registry,
            tool_registry=tool_registry,
            session=session,
            policy_evaluator=policy_evaluator,
            adapter_registry=adapter_registry,
            available_connectors=available_connectors,
        )
        graph = create_customer_support_escalation_graph(
            SupportEscalationGraphDependencies(tool_runtime=runtime)
        )
        graph_state = as_support_escalation_state(
            await graph.ainvoke(graph_input.to_initial_state())
        )
        response_draft: SupportResponseDraft | None = None
        if request.include_draft:
            response_draft = build_support_response_draft(graph_state)
        evidence_records = persist_support_evidence(session, run, graph_state)
        if response_draft is not None:
            evidence_records.append(persist_support_response_draft(session, run, response_draft))
        policy_decision_ids = collect_policy_decision_ids(graph_state)
        write_audit_event(
            session,
            AuditEventInput(
                run_id=run.id,
                workflow_id=run.workflow_id,
                event_type="workflow_graph.evidence_collected",
                actor_type="user" if request.actor_id else "system",
                actor_id=request.actor_id,
                action="workflow_graph.collect_support_context",
                resource_type="workflow_run",
                resource_id=str(run.id),
                trace_id=request.trace_id,
                payload={
                    "stage": (
                        "support_response_draft_created"
                        if response_draft is not None
                        else "support_context_collected"
                    ),
                    "evidence_count": len(evidence_records),
                    "tool_call_count": len(collect_tool_call_ids(graph_state)),
                    "policy_decision_ids": policy_decision_ids,
                    "response_draft_created": response_draft is not None,
                    "model_response_drafting_enabled": False,
                    "customer_message_enabled": False,
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
                action="workflow_graph.collect_support_context",
                resource_type="workflow_run",
                resource_id=str(run.id),
                trace_id=request.trace_id,
                payload={
                    "stage": "support_context_collection",
                    "error_type": type(exc).__name__,
                },
            ),
        )
        session.commit()
        raise

    customer_id = string_or_none(graph_state.get("ticket", {}).get("customer_id"))
    return SupportEscalationResponse(
        run_id=run.id,
        workflow_id=run.workflow_id,
        run_status=run.status,
        stage=(
            "support_response_draft_created"
            if response_draft is not None
            else "support_context_collected"
        ),
        ticket_id=graph_state["ticket_id"],
        customer_id=customer_id,
        knowledge_document_count=len(graph_state.get("knowledge_documents", [])),
        tool_call_ids=collect_tool_call_ids(graph_state),
        policy_decision_ids=policy_decision_ids,
        evidence_records=[
            SupportEvidenceRecordSummary(
                id=record.id,
                kind=record.kind,
                source_system=record.source_system,
                source_uri=record.source_uri,
                title=record.title,
                content_hash=record.content_hash,
            )
            for record in evidence_records
        ],
        response_draft_created=response_draft is not None,
        response_draft=response_draft,
    )


async def request_support_approval_review(
    run_id: UUID,
    request: SupportApprovalReviewRequest,
    session: Session,
) -> SupportApprovalReviewResponse:
    run = session.get(WorkflowRun, run_id)
    if run is None:
        raise SupportEscalationRejectedError(
            reason_code="workflow_run_not_found",
            message="Workflow run was not found.",
            http_status=404,
        )
    ensure_run_can_request_support_approval(run)

    requested_at = utc_now()
    expires_at = requested_at + timedelta(hours=24)
    approval = Approval(
        id=uuid4(),
        run_id=run.id,
        status="pending",
        risk_class="external_message",
        requested_action="customer_message",
        requested_by=request.requested_by,
        request_payload={
            "schema_version": "customer_support_escalation.approval_review.v1",
            "response_draft": request.response_draft.model_dump(mode="json"),
            "approval_contract": {
                "approval_table": "approvals",
                "customer_message_enabled": False,
                "external_actions_enabled": False,
                "future_send_tool_approval_id_required": True,
            },
        },
        decision_payload={},
        requested_at=requested_at,
        expires_at=expires_at,
    )
    try:
        run.status = "waiting_for_approval"
        session.add(approval)
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
                    "requested_action": "customer_message",
                    "risk_class": "external_message",
                    "requested_by": request.requested_by,
                    "customer_message_enabled": False,
                    "external_actions_enabled": False,
                },
            ),
        )
        session.commit()
    except Exception:
        session.rollback()
        raise

    return SupportApprovalReviewResponse(
        run_id=run.id,
        workflow_id=run.workflow_id,
        run_status=run.status,
        approvals=[
            SupportApprovalReviewItem(
                id=approval.id,
                status=approval.status,
                requested_action="customer_message",
                risk_class="external_message",
                requested_by=approval.requested_by,
                requested_at=requested_at.isoformat(),
                expires_at=expires_at.isoformat(),
            )
        ],
    )


async def decide_support_approval(
    run_id: UUID,
    approval_id: UUID,
    request: SupportApprovalDecisionRequest,
    session: Session,
    policy_evaluator: SupportApprovalPolicyEvaluator,
) -> SupportApprovalDecisionResponse:
    approval = session.get(Approval, approval_id)
    if approval is None:
        raise SupportEscalationRejectedError(
            reason_code="approval_not_found",
            message="Approval record was not found.",
            http_status=404,
        )
    if approval.run_id != run_id:
        raise SupportEscalationRejectedError(
            reason_code="approval_run_mismatch",
            message="Approval record does not belong to this workflow run.",
        )
    run = session.get(WorkflowRun, run_id)
    if run is None:
        raise SupportEscalationRejectedError(
            reason_code="workflow_run_not_found",
            message="Workflow run was not found.",
            http_status=404,
        )
    ensure_support_approval_can_be_decided(run, approval)

    policy_input = build_support_approval_decision_policy_input(
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
                    "customer_message_enabled": False,
                    "external_actions_enabled": False,
                },
            ),
        )
        session.commit()
        raise SupportEscalationRejectedError(
            reason_code="approval_decision_policy_denied",
            message="OPA policy denied the support approval decision.",
            http_status=403,
        )

    decided_at = utc_now()
    approval.status = "approved" if request.decision == "approve" else "rejected"
    approval.approver_id = request.approver_id
    approval.policy_decision_id = decision.decision_id
    approval.decided_at = decided_at
    approval.decision_payload = {
        "schema_version": "customer_support_escalation.approval_decision.v1",
        "decision": request.decision,
        "decision_reason": request.decision_reason,
        "approver_id": request.approver_id,
        "policy": {
            "decision_id": decision.decision_id,
            "package_path": decision.package_path,
            "reason_codes": decision.reason_codes,
            "result": decision.result,
        },
        "customer_message_enabled": False,
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
                "customer_message_enabled": False,
                "external_actions_enabled": False,
            },
        ),
    )
    session.commit()

    return SupportApprovalDecisionResponse(
        approval_id=approval.id,
        run_id=run.id,
        workflow_id=run.workflow_id,
        run_status=run.status,
        requested_action="customer_message",
        approval_status=cast(SupportApprovalDecisionStatus, approval.status),
        approver_id=request.approver_id,
        decided_at=decided_at.isoformat(),
        policy_decision=SupportApprovalPolicyDecisionSummary(
            allowed=decision.allowed,
            requires_approval=decision.requires_approval,
            decision_id=decision.decision_id,
            reason_codes=decision.reason_codes,
        ),
    )


def ensure_run_can_collect_support_context(run: WorkflowRun) -> None:
    if run.workflow_id != CUSTOMER_SUPPORT_WORKFLOW_ID:
        raise SupportEscalationRejectedError(
            reason_code="workflow_not_supported",
            message="This runtime path only supports customer_support_escalation runs.",
        )
    if run.execution_mode != "live":
        raise SupportEscalationRejectedError(
            reason_code="execution_mode_not_supported",
            message="Support escalation runtime currently requires live mode.",
        )
    if run.status not in {"queued", "running"}:
        raise SupportEscalationRejectedError(
            reason_code="workflow_run_status_invalid",
            message=f"Workflow run status {run.status} cannot collect support context.",
        )


def ensure_run_can_request_support_approval(run: WorkflowRun) -> None:
    if run.workflow_id != CUSTOMER_SUPPORT_WORKFLOW_ID:
        raise SupportEscalationRejectedError(
            reason_code="workflow_not_supported",
            message="This runtime path only supports customer_support_escalation runs.",
        )
    if run.status not in {"running", "waiting_for_approval"}:
        raise SupportEscalationRejectedError(
            reason_code="workflow_run_status_invalid",
            message=f"Workflow run status {run.status} cannot request support approval.",
        )


def ensure_support_approval_can_be_decided(run: WorkflowRun, approval: Approval) -> None:
    if run.workflow_id != CUSTOMER_SUPPORT_WORKFLOW_ID:
        raise SupportEscalationRejectedError(
            reason_code="workflow_not_supported",
            message="This runtime path only supports customer_support_escalation runs.",
        )
    if approval.status != "pending":
        raise SupportEscalationRejectedError(
            reason_code="approval_not_pending",
            message="Only pending support approval records can be decided.",
        )
    if approval.requested_action != "customer_message":
        raise SupportEscalationRejectedError(
            reason_code="approval_action_not_supported",
            message="This runtime path only supports customer_message approvals.",
        )
    if approval.request_payload.get("schema_version") != (
        "customer_support_escalation.approval_review.v1"
    ):
        raise SupportEscalationRejectedError(
            reason_code="approval_payload_invalid",
            message="Approval payload is not a Support approval-review record.",
        )


def build_graph_input_from_run(
    run: WorkflowRun,
    request: SupportEscalationRequest,
) -> SupportEscalationInput:
    input_payload = run.input_payload or {}
    ticket_id = request.ticket_id or string_or_none(input_payload.get("ticket_id"))
    if ticket_id is None:
        raise SupportEscalationRejectedError(
            reason_code="ticket_id_missing",
            message="ticket_id is required in the request or stored run input.",
            http_status=422,
        )
    locale = request.locale or string_or_none(input_payload.get("locale"))
    return SupportEscalationInput(
        run_id=run.id,
        ticket_id=ticket_id,
        locale=locale,
        autonomy_level=cast_autonomy_level(run.autonomy_level),
        actor_id=request.actor_id,
        trace_id=request.trace_id,
    )


def persist_support_evidence(
    session: Session,
    run: WorkflowRun,
    state: SupportEscalationState,
) -> list[EvidenceRecord]:
    records: list[EvidenceRecord] = []
    for evidence in state.get("evidence", []):
        payload = evidence.get("payload", {})
        if not isinstance(payload, dict):
            payload = {}
        content_hash = hash_payload(payload)
        record = EvidenceRecord(
            id=uuid4(),
            run_id=run.id,
            workflow_id=run.workflow_id,
            kind=support_evidence_record_kind(str(evidence["kind"])),
            source_system=str(evidence["source_system"]),
            source_uri=string_or_none(evidence.get("source_uri")),
            title=str(evidence["title"]),
            content_hash=content_hash,
            evidence_metadata={
                "schema_version": "customer_support_escalation.evidence.v1",
                "evidence_kind": str(evidence["kind"]),
                "payload_hash": content_hash,
                "raw_payload_persisted": False,
                "customer_data_redacted": evidence["source_system"] in {"support_system", "crm"},
                "response_drafting_enabled": False,
                "customer_message_enabled": False,
                "write_actions_enabled": False,
            },
            captured_at=utc_now(),
        )
        session.add(record)
        records.append(record)
    session.flush()
    return records


def persist_support_response_draft(
    session: Session,
    run: WorkflowRun,
    response_draft: SupportResponseDraft,
) -> EvidenceRecord:
    payload = response_draft.model_dump(mode="json")
    record = EvidenceRecord(
        id=uuid4(),
        run_id=run.id,
        workflow_id=run.workflow_id,
        kind="document",
        source_system="aegisops",
        source_uri=f"aegisops://workflow-runs/{run.id}/support-response-draft",
        title=f"Support response draft for {response_draft.ticket_id}",
        content_hash=hash_payload(payload),
        evidence_metadata={
            "schema_version": response_draft.schema_version,
            "ticket_id": response_draft.ticket_id,
            "customer_id": response_draft.customer_id,
            "citation_count": len(response_draft.citation_uris),
            "requires_human_review": response_draft.requires_human_review,
            "customer_message_enabled": response_draft.customer_message_enabled,
            "external_actions_enabled": response_draft.external_actions_enabled,
        },
        captured_at=utc_now(),
    )
    session.add(record)
    session.flush()
    return record


def build_support_response_draft(state: SupportEscalationState) -> SupportResponseDraft:
    ticket = state.get("ticket", {})
    documents = state.get("knowledge_documents", [])
    citations = [
        SupportDraftCitation(
            document_id=string_or_none(document.get("document_id")) or "knowledge-document",
            title=string_or_none(document.get("title")) or "Knowledge document",
            source_uri=source_uri,
        )
        for document in documents
        if (source_uri := string_or_none(document.get("source_uri"))) is not None
    ]
    if not citations:
        raise SupportEscalationRejectedError(
            reason_code="knowledge_citations_missing",
            message="A support response draft requires at least one cited knowledge source.",
            http_status=422,
        )

    ticket_id = string_or_none(ticket.get("ticket_id")) or state["ticket_id"]
    subject = string_or_none(ticket.get("subject")) or "support escalation"
    customer_id = string_or_none(ticket.get("customer_id"))
    primary_citation = citations[0]
    response_body = (
        f"Thanks for contacting support about {subject}. "
        f"Based on the approved article \"{primary_citation.title}\", our team should verify "
        "the documented resolution steps before sending final guidance. A human support lead "
        "must review this draft and citations before it is sent to the customer."
    )
    return SupportResponseDraft(
        ticket_id=ticket_id,
        customer_id=customer_id,
        subject=subject,
        response_body=response_body,
        citation_uris=[citation.source_uri for citation in citations],
        cited_documents=citations,
    )


def hash_payload(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256(encoded).hexdigest()


def support_evidence_record_kind(evidence_kind: str) -> str:
    if evidence_kind == "knowledge_base_document":
        return "document"
    return "api_response"


def cast_autonomy_level(value: str) -> AutonomyLevel:
    if value not in {"read_only", "draft_only", "approval_required", "autonomous"}:
        raise SupportEscalationRejectedError(
            reason_code="autonomy_level_invalid",
            message=f"Workflow run autonomy level {value} is not supported.",
        )
    return cast(AutonomyLevel, value)


def build_support_approval_decision_policy_input(
    run: WorkflowRun,
    approval: Approval,
    request: SupportApprovalDecisionRequest,
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
            "write_actions_enabled": extract_support_write_actions_enabled(
                approval.request_payload
            ),
            "request_payload": approval.request_payload,
        },
    }


def extract_support_write_actions_enabled(request_payload: dict[str, Any]) -> bool:
    approval_contract = request_payload.get("approval_contract", {})
    if not isinstance(approval_contract, dict):
        return True
    return bool(approval_contract.get("external_actions_enabled", True))
