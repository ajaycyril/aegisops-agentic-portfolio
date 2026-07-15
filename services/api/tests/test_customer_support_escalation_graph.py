from typing import Any
from uuid import UUID, uuid4

import pytest

from aegisops_api.tools import (
    ToolCallAuthorizationRequest,
    ToolCallAuthorizationResponse,
    ToolCallExecutionRequest,
    ToolCallExecutionResponse,
)
from aegisops_api.tools.execution import ToolPolicyDecisionSummary
from aegisops_api.workflows.customer_support_escalation import (
    SupportEscalationGraphDependencies,
    SupportEscalationInput,
    as_support_escalation_state,
    create_customer_support_escalation_graph,
)


class FakeSupportToolRuntime:
    def __init__(self) -> None:
        self.tool_by_call_id: dict[UUID, str] = {}
        self.run_by_call_id: dict[UUID, UUID] = {}
        self.authorized_inputs: list[dict[str, Any]] = []
        self.executed_inputs: list[dict[str, Any]] = []

    async def authorize_tool_call(
        self,
        request: ToolCallAuthorizationRequest,
    ) -> ToolCallAuthorizationResponse:
        tool_call_id = uuid4()
        self.tool_by_call_id[tool_call_id] = request.tool_id
        self.run_by_call_id[tool_call_id] = request.run_id
        self.authorized_inputs.append(
            {
                "tool_id": request.tool_id,
                "input_payload": request.input_payload,
                "autonomy_level": request.autonomy_level,
            }
        )
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
        self.executed_inputs.append({"tool_id": tool_id, "input_payload": request.input_payload})
        if tool_id == "support_ticket_read":
            output_payload: dict[str, Any] = {
                "ticket": {
                    "ticket_id": "TCK-1024",
                    "subject": "SSO lockout after domain migration",
                    "customer_id": "cus_123",
                    "product": "Identity",
                    "category": "Authentication",
                    "priority": "high",
                    "tags": ["sso", "migration"],
                    "source_uri": "https://support.example/tickets/TCK-1024",
                }
            }
        elif tool_id == "crm_customer_profile_read":
            output_payload = {
                "customer": {
                    "customer_id": "cus_123",
                    "account_id": "acct_456",
                    "plan": "enterprise",
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


@pytest.mark.asyncio
async def test_support_graph_collects_ticket_customer_and_knowledge_evidence() -> None:
    runtime = FakeSupportToolRuntime()
    graph = create_customer_support_escalation_graph(
        SupportEscalationGraphDependencies(tool_runtime=runtime)
    )
    graph_input = SupportEscalationInput(
        run_id=uuid4(),
        ticket_id="TCK-1024",
        locale="en-US",
        autonomy_level="draft_only",
        actor_id="support-lead-1",
    )

    result = as_support_escalation_state(await graph.ainvoke(graph_input.to_initial_state()))

    assert result["ticket"]["ticket_id"] == "TCK-1024"
    assert result["customer_profile"]["customer_id"] == "cus_123"
    assert result["knowledge_documents"][0]["document_id"] == "kb_42"
    assert [item["kind"] for item in result["evidence"]] == [
        "support_ticket",
        "crm_customer_profile",
        "knowledge_base_document",
    ]
    assert [call["tool_id"] for call in runtime.authorized_inputs] == [
        "support_ticket_read",
        "crm_customer_profile_read",
        "knowledge_base_search",
    ]
    assert runtime.authorized_inputs[2]["input_payload"] == {
        "query": (
            "SSO lockout after domain migration | Identity | Authentication | high | "
            "sso | migration"
        ),
        "limit": 5,
        "product": "Identity",
        "locale": "en-US",
    }
    assert [
        {"tool_id": call["tool_id"], "input_payload": call["input_payload"]}
        for call in runtime.authorized_inputs
    ] == runtime.executed_inputs


def test_support_input_requires_ticket_id() -> None:
    with pytest.raises(ValueError):
        SupportEscalationInput(run_id=uuid4(), ticket_id="")
