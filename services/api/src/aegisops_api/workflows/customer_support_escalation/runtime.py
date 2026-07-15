from __future__ import annotations

import json
from hashlib import sha256
from typing import Any, Literal, cast
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from aegisops_api.audit import AuditEventInput, write_audit_event
from aegisops_api.db.models import EvidenceRecord, WorkflowRun, utc_now
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

SupportRunStage = Literal["support_context_collected"]


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
    response_drafting_enabled: Literal[False] = False
    customer_message_enabled: Literal[False] = False
    write_actions_enabled: Literal[False] = False


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
        evidence_records = persist_support_evidence(session, run, graph_state)
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
                    "stage": "support_context_collected",
                    "evidence_count": len(evidence_records),
                    "tool_call_count": len(collect_tool_call_ids(graph_state)),
                    "policy_decision_ids": policy_decision_ids,
                    "response_drafting_enabled": False,
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
        stage="support_context_collected",
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
