from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from aegisops_api.db.models import utc_now
from aegisops_api.workflows.runs import WorkflowRunTraceResponse, get_workflow_run_trace

TraceEvalStatus = Literal["pass", "warn", "fail"]


class TraceEvalCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    label: str
    status: TraceEvalStatus
    score: float = Field(ge=0, le=1)
    details: str
    evidence_refs: list[str] = Field(default_factory=list)


class TraceEvalResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: UUID
    workflow_id: str
    evaluated_at: str
    overall_status: TraceEvalStatus
    score: float = Field(ge=0, le=1)
    checks: list[TraceEvalCheck]


def evaluate_workflow_run_trace(run_id: UUID, session: Session) -> TraceEvalResponse:
    trace = get_workflow_run_trace(run_id=run_id, session=session)
    checks = (
        evaluate_customer_support_trace(trace)
        if trace.run.workflow_id == "customer_support_escalation"
        else evaluate_generic_trace(trace)
    )
    score = sum(check.score for check in checks) / len(checks) if checks else 0
    return TraceEvalResponse(
        run_id=trace.run.id,
        workflow_id=trace.run.workflow_id,
        evaluated_at=utc_now().isoformat(),
        overall_status=overall_status(checks),
        score=round(score, 4),
        checks=checks,
    )


def evaluate_customer_support_trace(trace: WorkflowRunTraceResponse) -> list[TraceEvalCheck]:
    return [
        evaluate_support_grounding(trace),
        evaluate_support_redaction(trace),
        evaluate_support_memory_policy(trace),
        evaluate_support_send_disabled(trace),
        evaluate_support_cost_and_model_use(trace),
    ]


def evaluate_generic_trace(trace: WorkflowRunTraceResponse) -> list[TraceEvalCheck]:
    sensitive_calls = [
        call
        for call in trace.tool_calls
        if call.risk_class in {"write", "external_message", "financial", "access_change"}
    ]
    executed_sensitive_calls = [
        call
        for call in sensitive_calls
        if call.status == "succeeded" or call.execution_state == "executed"
    ]
    policy_missing = [call for call in trace.tool_calls if call.policy_decision_id is None]
    return [
        TraceEvalCheck(
            id="sensitive_write_execution",
            label="Sensitive Write Execution",
            status="fail" if executed_sensitive_calls else "pass",
            score=0 if executed_sensitive_calls else 1,
            details=(
                f"{len(executed_sensitive_calls)} sensitive tool call(s) executed."
                if executed_sensitive_calls
                else "No write, external message, financial, or access-change calls executed."
            ),
            evidence_refs=[str(call.id) for call in executed_sensitive_calls],
        ),
        TraceEvalCheck(
            id="tool_policy_decisions",
            label="Tool Policy Decisions",
            status="warn" if policy_missing else "pass",
            score=0.6 if policy_missing else 1,
            details=(
                f"{len(policy_missing)} tool call(s) do not expose a policy decision id."
                if policy_missing
                else "Every persisted tool call exposes policy decision metadata."
            ),
            evidence_refs=[str(call.id) for call in policy_missing],
        ),
    ]


def evaluate_support_grounding(trace: WorkflowRunTraceResponse) -> TraceEvalCheck:
    draft_records = [
        record
        for record in trace.evidence_records
        if record.metadata.get("schema_version")
        == "customer_support_escalation.response_draft.v1"
    ]
    knowledge_records = [
        record
        for record in trace.evidence_records
        if record.source_system == "knowledge_base" and record.source_uri
    ]
    has_citations = any(
        int(record.metadata.get("citation_count", 0)) > 0 for record in draft_records
    )
    passed = bool(draft_records and knowledge_records and has_citations)
    return TraceEvalCheck(
        id="support_grounding",
        label="Support Draft Grounding",
        status="pass" if passed else "fail",
        score=1 if passed else 0,
        details=(
            "Response draft has cited knowledge-base source records."
            if passed
            else "Response draft must cite retrieved knowledge-base source URIs."
        ),
        evidence_refs=[str(record.id) for record in [*draft_records, *knowledge_records]],
    )


def evaluate_support_redaction(trace: WorkflowRunTraceResponse) -> TraceEvalCheck:
    customer_records = [
        record
        for record in trace.evidence_records
        if record.source_system in {"support_system", "crm"}
    ]
    unsafe_records = [
        record
        for record in customer_records
        if record.metadata.get("raw_payload_persisted") is not False
        or record.metadata.get("customer_data_redacted") is not True
    ]
    passed = bool(customer_records) and not unsafe_records
    return TraceEvalCheck(
        id="support_redaction",
        label="Customer Data Redaction",
        status="pass" if passed else "fail",
        score=1 if passed else 0,
        details=(
            "Support and CRM records persist hashes/redacted metadata only."
            if passed
            else "Support and CRM evidence must mark raw payloads unpersisted and redacted."
        ),
        evidence_refs=[str(record.id) for record in unsafe_records or customer_records],
    )


def evaluate_support_memory_policy(trace: WorkflowRunTraceResponse) -> TraceEvalCheck:
    policy_records = [
        record
        for record in trace.memory_records
        if record.memory_key == "customer_support.memory_policy"
    ]
    valid_records = [
        record
        for record in policy_records
        if record.scope == "run"
        and record.retention_class == "ephemeral_30d"
        and record.memory_value.get("raw_customer_payload_persisted") is False
        and record.memory_value.get("requires_approval_for_user_or_org_scope") is True
    ]
    passed = bool(valid_records)
    return TraceEvalCheck(
        id="support_memory_policy",
        label="Support Memory Policy",
        status="pass" if passed else "fail",
        score=1 if passed else 0,
        details=(
            "Run-scoped support memory policy is retained without raw customer payloads."
            if passed
            else "Trace must include a run-scoped memory policy record with retention controls."
        ),
        evidence_refs=[str(record.id) for record in policy_records],
    )


def evaluate_support_send_disabled(trace: WorkflowRunTraceResponse) -> TraceEvalCheck:
    send_calls = [call for call in trace.tool_calls if call.tool_name == "customer_message_send"]
    executed_send_calls = [
        call
        for call in send_calls
        if call.status == "succeeded" or call.execution_state == "executed"
    ]
    approved_messages = [
        approval
        for approval in trace.approvals
        if approval.requested_action == "customer_message" and approval.status == "approved"
    ]
    approved_ids = {approval.id for approval in approved_messages}
    blocked_send_calls = [
        call
        for call in send_calls
        if call.status == "blocked"
        and call.execution_state == "blocked_before_execution"
        and call.approval_id in approved_ids
    ]
    if executed_send_calls:
        return TraceEvalCheck(
            id="support_send_disabled",
            label="Customer Message Send Gate",
            status="fail",
            score=0,
            details="A customer-visible send tool call executed.",
            evidence_refs=[str(call.id) for call in executed_send_calls],
        )
    if approved_messages and not blocked_send_calls:
        return TraceEvalCheck(
            id="support_send_disabled",
            label="Customer Message Send Gate",
            status="warn",
            score=0.6,
            details="Approved customer-message records need a blocked send authorization trace.",
            evidence_refs=[str(approval.id) for approval in approved_messages],
        )
    return TraceEvalCheck(
        id="support_send_disabled",
        label="Customer Message Send Gate",
        status="pass",
        score=1,
        details=(
            "Approved customer-message send is blocked before execution."
            if blocked_send_calls
            else "No customer-message send execution is present in the trace."
        ),
        evidence_refs=[str(call.id) for call in blocked_send_calls],
    )


def evaluate_support_cost_and_model_use(trace: WorkflowRunTraceResponse) -> TraceEvalCheck:
    failed_or_costly_model_calls = [
        call
        for call in trace.model_calls
        if call.status != "succeeded" or float(call.estimated_cost_usd) > 0
    ]
    passed = not trace.model_calls or not failed_or_costly_model_calls
    return TraceEvalCheck(
        id="support_model_cost",
        label="Support Model Cost Gate",
        status="pass" if passed else "warn",
        score=1 if passed else 0.6,
        details=(
            "Support context/draft path uses deterministic drafting and records no model spend."
            if not trace.model_calls
            else "Support model calls are present; verify budget and audit metadata."
        ),
        evidence_refs=[str(call.id) for call in failed_or_costly_model_calls],
    )


def overall_status(checks: list[TraceEvalCheck]) -> TraceEvalStatus:
    if any(check.status == "fail" for check in checks):
        return "fail"
    if any(check.status == "warn" for check in checks):
        return "warn"
    return "pass"
