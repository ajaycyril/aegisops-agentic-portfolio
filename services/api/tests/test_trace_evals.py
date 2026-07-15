from collections.abc import Sequence
from typing import cast
from uuid import uuid4

from sqlalchemy.orm import Session

from aegisops_api.db.models import (
    Approval,
    AuditEvent,
    EvidenceRecord,
    MemoryRecord,
    ModelCall,
    ToolCall,
    WorkflowRun,
    utc_now,
)
from aegisops_api.evals import evaluate_workflow_run_trace


class ListResult:
    def __init__(self, values: Sequence[object]) -> None:
        self._values = values

    def scalars(self) -> Sequence[object]:
        return self._values


class TraceEvalSession:
    def __init__(self, run: WorkflowRun, query_results: Sequence[Sequence[object]]) -> None:
        self.run = run
        self.query_results = query_results
        self.execute_count = 0

    def get(self, model: object, _identifier: object) -> object | None:
        if model is WorkflowRun:
            return self.run
        return None

    def execute(self, _statement: object) -> ListResult:
        result = self.query_results[self.execute_count]
        self.execute_count += 1
        return ListResult(result)


def create_support_trace_records(include_blocked_send: bool = True) -> tuple[
    WorkflowRun,
    list[Approval],
    list[ToolCall],
    list[ModelCall],
    list[EvidenceRecord],
    list[MemoryRecord],
    list[AuditEvent],
]:
    now = utc_now()
    run = WorkflowRun(
        id=uuid4(),
        workflow_id="customer_support_escalation",
        registry_snapshot_id=uuid4(),
        status="waiting_for_approval",
        execution_mode="live",
        autonomy_level="draft_only",
        input_payload={"ticket_id": "TCK-1024"},
        budget={},
        policy_context={},
        started_at=now,
        updated_at=now,
    )
    approval = Approval(
        id=uuid4(),
        run_id=run.id,
        status="approved",
        risk_class="external_message",
        requested_action="customer_message",
        requested_by="support-agent",
        approver_id="support-lead",
        requested_at=now,
        decided_at=now,
    )
    tool_calls: list[ToolCall] = []
    if include_blocked_send:
        tool_calls.append(
            ToolCall(
                id=uuid4(),
                run_id=run.id,
                approval_id=approval.id,
                tool_name="customer_message_send",
                tool_version="disabled-contract-v1",
                risk_class="external_message",
                input_schema_hash="schema",
                input_hash="input",
                status="blocked",
                policy_decision_id="support-approval-decision",
                started_at=now,
                call_metadata={"execution_state": "blocked_before_execution"},
            )
        )
    evidence = [
        EvidenceRecord(
            id=uuid4(),
            run_id=run.id,
            workflow_id=run.workflow_id,
            kind="api_response",
            source_system="support_system",
            source_uri="https://support.example/tickets/TCK-1024",
            title="Support ticket TCK-1024",
            content_hash="ticket-hash",
            evidence_metadata={
                "raw_payload_persisted": False,
                "customer_data_redacted": True,
            },
            captured_at=now,
            created_at=now,
        ),
        EvidenceRecord(
            id=uuid4(),
            run_id=run.id,
            workflow_id=run.workflow_id,
            kind="api_response",
            source_system="crm",
            source_uri="https://crm.example/customers/customer",
            title="CRM customer profile",
            content_hash="crm-hash",
            evidence_metadata={
                "raw_payload_persisted": False,
                "customer_data_redacted": True,
            },
            captured_at=now,
            created_at=now,
        ),
        EvidenceRecord(
            id=uuid4(),
            run_id=run.id,
            workflow_id=run.workflow_id,
            kind="document",
            source_system="knowledge_base",
            source_uri="https://kb.example/articles/kb_42",
            title="Troubleshoot enterprise SSO lockouts",
            content_hash="kb-hash",
            evidence_metadata={},
            captured_at=now,
            created_at=now,
        ),
        EvidenceRecord(
            id=uuid4(),
            run_id=run.id,
            workflow_id=run.workflow_id,
            kind="document",
            source_system="aegisops",
            source_uri=f"aegisops://workflow-runs/{run.id}/support-response-draft",
            title="Support response draft",
            content_hash="draft-hash",
            evidence_metadata={
                "schema_version": "customer_support_escalation.response_draft.v1",
                "citation_count": 1,
                "customer_message_enabled": False,
                "external_actions_enabled": False,
            },
            captured_at=now,
            created_at=now,
        ),
    ]
    memory = [
        MemoryRecord(
            id=uuid4(),
            run_id=run.id,
            workflow_id=run.workflow_id,
            scope="run",
            subject_id="customer_hash:abc123",
            memory_key="customer_support.memory_policy",
            memory_value={
                "raw_customer_payload_persisted": False,
                "requires_approval_for_user_or_org_scope": True,
            },
            retention_class="ephemeral_30d",
            data_sensitivity="confidential",
            source_evidence_id=evidence[0].id,
            created_at=now,
        )
    ]
    model_calls: list[ModelCall] = []
    audit_events: list[AuditEvent] = []
    return run, [approval], tool_calls, model_calls, evidence, memory, audit_events


def test_support_trace_eval_passes_with_grounding_memory_and_blocked_send() -> None:
    records = create_support_trace_records(include_blocked_send=True)
    run, approvals, tool_calls, model_calls, evidence, memory, audit_events = records
    session = TraceEvalSession(
        run,
        [approvals, tool_calls, model_calls, evidence, memory, audit_events],
    )

    response = evaluate_workflow_run_trace(run.id, cast(Session, session))

    assert response.workflow_id == "customer_support_escalation"
    assert response.overall_status == "pass"
    assert response.score == 1
    assert {check.id: check.status for check in response.checks} == {
        "support_grounding": "pass",
        "support_redaction": "pass",
        "support_memory_policy": "pass",
        "support_send_disabled": "pass",
        "support_model_cost": "pass",
    }


def test_support_trace_eval_warns_when_approved_message_lacks_blocked_send() -> None:
    records = create_support_trace_records(include_blocked_send=False)
    run, approvals, tool_calls, model_calls, evidence, memory, audit_events = records
    session = TraceEvalSession(
        run,
        [approvals, tool_calls, model_calls, evidence, memory, audit_events],
    )

    response = evaluate_workflow_run_trace(run.id, cast(Session, session))

    assert response.overall_status == "warn"
    send_check = next(check for check in response.checks if check.id == "support_send_disabled")
    assert send_check.status == "warn"
    assert send_check.score == 0.6
