from typing import Any, cast
from uuid import UUID, uuid4

import pytest

from aegisops_api.db.models import Approval, EvidenceRecord, WorkflowRun
from aegisops_api.tools import (
    ToolCallAuthorizationRequest,
    ToolCallAuthorizationResponse,
    ToolCallExecutionRequest,
    ToolCallExecutionResponse,
)
from aegisops_api.tools.adapters import ToolAdapterRegistry
from aegisops_api.tools.execution import ToolPolicyDecisionSummary
from aegisops_api.tools.registry import ToolRegistry
from aegisops_api.workflows.customer_support_escalation import (
    SupportApprovalReviewRequest,
    SupportDraftCitation,
    SupportEscalationRejectedError,
    SupportEscalationRequest,
    SupportResponseDraft,
    collect_support_escalation_context,
    request_support_approval_review,
)
from aegisops_api.workflows.registry import WorkflowRegistry


class FakeSupportToolRuntime:
    def __init__(self) -> None:
        self.tool_by_call_id: dict[UUID, str] = {}
        self.run_by_call_id: dict[UUID, UUID] = {}

    async def authorize_tool_call(
        self,
        request: ToolCallAuthorizationRequest,
    ) -> ToolCallAuthorizationResponse:
        tool_call_id = uuid4()
        self.tool_by_call_id[tool_call_id] = request.tool_id
        self.run_by_call_id[tool_call_id] = request.run_id
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
        _request: ToolCallExecutionRequest,
    ) -> ToolCallExecutionResponse:
        tool_id = self.tool_by_call_id[tool_call_id]
        if tool_id == "support_ticket_read":
            output_payload: dict[str, Any] = {
                "ticket": {
                    "ticket_id": "TCK-1024",
                    "subject": "raw ticket subject should not be persisted in metadata",
                    "customer_id": "cus_123",
                    "product": "Identity",
                    "source_uri": "https://support.example/tickets/TCK-1024",
                }
            }
        elif tool_id == "crm_customer_profile_read":
            output_payload = {
                "customer": {
                    "customer_id": "cus_123",
                    "account_name": "raw account name should not be persisted in metadata",
                    "source_uri": "https://crm.example/customers/cus_123",
                }
            }
        else:
            output_payload = {
                "documents": [
                    {
                        "document_id": "kb_42",
                        "title": "Troubleshoot enterprise SSO lockouts",
                        "excerpt": "Verify IdP domain migration and SCIM sync state.",
                        "source_uri": "https://kb.example/articles/kb_42",
                    }
                ]
            }
        return ToolCallExecutionResponse(
            id=tool_call_id,
            run_id=self.run_by_call_id[tool_call_id],
            workflow_id="customer_support_escalation",
            tool_id=tool_id,
            status="succeeded",
            execution_state="executed",
            output_hash="hash",
            output_payload=output_payload,
            latency_ms=7,
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

    def rollback(self) -> None:
        pass

    def get(self, model: object, identifier: object) -> object | None:
        if model is WorkflowRun:
            return self.runs.get(cast(UUID, identifier))
        return None


def create_support_run(input_payload: dict[str, Any] | None = None) -> WorkflowRun:
    return WorkflowRun(
        id=uuid4(),
        workflow_id="customer_support_escalation",
        registry_snapshot_id=uuid4(),
        status="queued",
        execution_mode="live",
        autonomy_level="draft_only",
        input_payload=input_payload if input_payload is not None else {"ticket_id": "TCK-1024"},
        budget={"max_tool_calls": 25, "max_run_seconds": 300, "max_estimated_usd": 1.0},
        policy_context={},
    )


@pytest.mark.asyncio
async def test_collect_support_context_creates_grounded_draft_and_redacted_metadata() -> None:
    run = create_support_run()
    session = RuntimeSession({run.id: run})

    response = await collect_support_escalation_context(
        run_id=run.id,
        request=SupportEscalationRequest(actor_id="support-lead-1", include_draft=True),
        session=cast(Any, session),
        workflow_registry=cast(WorkflowRegistry, object()),
        tool_registry=cast(ToolRegistry, object()),
        policy_evaluator=cast(Any, object()),
        adapter_registry=cast(ToolAdapterRegistry, object()),
        available_connectors={"support_system", "crm", "knowledge_base"},
        tool_runtime=FakeSupportToolRuntime(),
    )

    evidence_records = [
        instance for instance in session.added if isinstance(instance, EvidenceRecord)
    ]
    assert response.stage == "support_response_draft_created"
    assert response.customer_id == "cus_123"
    assert response.knowledge_document_count == 1
    assert response.response_draft_created is True
    assert response.response_draft is not None
    assert response.response_draft.requires_human_review is True
    assert response.response_draft.citation_uris == ["https://kb.example/articles/kb_42"]
    assert response.model_response_drafting_enabled is False
    assert response.customer_message_enabled is False
    assert len(response.tool_call_ids) == 3
    assert len(evidence_records) == 4
    assert {record.kind for record in evidence_records} == {
        "api_response",
        "document",
    }
    assert evidence_records[0].evidence_metadata["raw_payload_persisted"] is False
    assert evidence_records[0].evidence_metadata["customer_data_redacted"] is True
    assert evidence_records[0].evidence_metadata["evidence_kind"] == "support_ticket"
    assert "raw ticket subject" not in str(evidence_records[0].evidence_metadata)
    assert run.status == "running"
    assert session.commit_count == 1


@pytest.mark.asyncio
async def test_request_support_approval_review_creates_pending_customer_message() -> None:
    run = create_support_run()
    run.status = "running"
    session = RuntimeSession({run.id: run})
    draft = SupportResponseDraft(
        ticket_id="TCK-1024",
        customer_id="cus_123",
        subject="SSO lockout",
        response_body="Human-reviewed response draft.",
        citation_uris=["https://kb.example/articles/kb_42"],
        cited_documents=[
            SupportDraftCitation(
                document_id="kb_42",
                title="Troubleshoot enterprise SSO lockouts",
                source_uri="https://kb.example/articles/kb_42",
            )
        ],
    )

    response = await request_support_approval_review(
        run_id=run.id,
        request=SupportApprovalReviewRequest(
            response_draft=draft,
            requested_by="support-agent",
            actor_id="support-lead-1",
        ),
        session=cast(Any, session),
    )

    approvals = [instance for instance in session.added if isinstance(instance, Approval)]
    assert response.run_status == "waiting_for_approval"
    assert response.customer_message_enabled is False
    assert len(response.approvals) == 1
    assert response.approvals[0].requested_action == "customer_message"
    assert approvals[0].risk_class == "external_message"
    assert approvals[0].request_payload["response_draft"]["ticket_id"] == "TCK-1024"
    assert run.status == "waiting_for_approval"


@pytest.mark.asyncio
async def test_collect_support_context_rejects_replay_until_captured_schema_exists() -> None:
    run = create_support_run()
    run.execution_mode = "replay"
    session = RuntimeSession({run.id: run})

    with pytest.raises(SupportEscalationRejectedError) as exc_info:
        await collect_support_escalation_context(
            run_id=run.id,
            request=SupportEscalationRequest(),
            session=cast(Any, session),
            workflow_registry=cast(WorkflowRegistry, object()),
            tool_registry=cast(ToolRegistry, object()),
            policy_evaluator=cast(Any, object()),
            adapter_registry=cast(ToolAdapterRegistry, object()),
            available_connectors=set(),
            tool_runtime=FakeSupportToolRuntime(),
        )

    assert exc_info.value.reason_code == "execution_mode_not_supported"
