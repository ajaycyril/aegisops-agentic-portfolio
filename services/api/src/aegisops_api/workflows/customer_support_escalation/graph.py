from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Protocol, TypedDict, cast
from uuid import UUID

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from aegisops_api.budget import BudgetPolicyEvaluator
from aegisops_api.tools import (
    ToolCallAuthorizationRequest,
    ToolCallAuthorizationResponse,
    ToolCallExecutionRequest,
    ToolCallExecutionResponse,
    ToolPolicyEvaluator,
    authorize_tool_call,
    execute_authorized_tool_call,
)
from aegisops_api.tools.adapters import ToolAdapterRegistry
from aegisops_api.tools.registry import ToolRegistry
from aegisops_api.workflows.registry import AutonomyLevel, WorkflowRegistry

CUSTOMER_SUPPORT_WORKFLOW_ID = "customer_support_escalation"


class SupportEscalationGraphError(RuntimeError):
    pass


class SupportEscalationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: UUID
    ticket_id: str = Field(min_length=1)
    locale: str | None = Field(default=None, min_length=1)
    autonomy_level: AutonomyLevel = "read_only"
    actor_id: str | None = None
    trace_id: str | None = None

    def to_initial_state(self) -> SupportEscalationState:
        return {
            "run_id": self.run_id,
            "workflow_id": CUSTOMER_SUPPORT_WORKFLOW_ID,
            "ticket_id": self.ticket_id,
            "locale": self.locale,
            "autonomy_level": self.autonomy_level,
            "actor_id": self.actor_id,
            "trace_id": self.trace_id,
            "ticket": {},
            "customer_profile": {},
            "knowledge_documents": [],
            "ticket_tool_call_ids": [],
            "customer_tool_call_ids": [],
            "knowledge_tool_call_ids": [],
            "ticket_policy_decision_ids": [],
            "customer_policy_decision_ids": [],
            "knowledge_policy_decision_ids": [],
            "evidence": [],
        }


class SupportEscalationState(TypedDict, total=False):
    run_id: UUID
    workflow_id: str
    ticket_id: str
    locale: str | None
    autonomy_level: AutonomyLevel
    actor_id: str | None
    trace_id: str | None
    ticket: dict[str, Any]
    customer_profile: dict[str, Any]
    knowledge_documents: list[dict[str, Any]]
    ticket_tool_call_ids: list[str]
    customer_tool_call_ids: list[str]
    knowledge_tool_call_ids: list[str]
    ticket_policy_decision_ids: list[str]
    customer_policy_decision_ids: list[str]
    knowledge_policy_decision_ids: list[str]
    evidence: list[dict[str, Any]]


class SupportEscalationToolRuntime(Protocol):
    async def authorize_tool_call(
        self,
        request: ToolCallAuthorizationRequest,
    ) -> ToolCallAuthorizationResponse:
        pass

    async def execute_tool_call(
        self,
        tool_call_id: UUID,
        request: ToolCallExecutionRequest,
    ) -> ToolCallExecutionResponse:
        pass


@dataclass(frozen=True)
class PolicyBackedSupportToolRuntime:
    workflow_registry: WorkflowRegistry
    tool_registry: ToolRegistry
    session: Session
    policy_evaluator: ToolPolicyEvaluator
    adapter_registry: ToolAdapterRegistry
    available_connectors: set[str]
    budget_evaluator: BudgetPolicyEvaluator | None = None

    async def authorize_tool_call(
        self,
        request: ToolCallAuthorizationRequest,
    ) -> ToolCallAuthorizationResponse:
        return await authorize_tool_call(
            request=request,
            workflow_registry=self.workflow_registry,
            tool_registry=self.tool_registry,
            session=self.session,
            policy_evaluator=self.policy_evaluator,
            available_connectors=self.available_connectors,
            budget_evaluator=self.budget_evaluator,
        )

    async def execute_tool_call(
        self,
        tool_call_id: UUID,
        request: ToolCallExecutionRequest,
    ) -> ToolCallExecutionResponse:
        return await execute_authorized_tool_call(
            tool_call_id=tool_call_id,
            request=request,
            tool_registry=self.tool_registry,
            session=self.session,
            adapter_registry=self.adapter_registry,
            budget_evaluator=self.budget_evaluator,
        )


@dataclass(frozen=True)
class SupportEscalationGraphDependencies:
    tool_runtime: SupportEscalationToolRuntime


def create_customer_support_escalation_graph(
    dependencies: SupportEscalationGraphDependencies,
) -> Any:
    graph = StateGraph(SupportEscalationState)
    graph.add_node(
        "ticket_reader",
        cast(Any, create_ticket_reader_node(dependencies.tool_runtime)),
    )
    graph.add_node(
        "customer_context_reader",
        cast(Any, create_customer_context_reader_node(dependencies.tool_runtime)),
    )
    graph.add_node(
        "knowledge_searcher",
        cast(Any, create_knowledge_searcher_node(dependencies.tool_runtime)),
    )
    graph.add_node("evidence_auditor", cast(Any, evidence_auditor_node))
    graph.add_edge(START, "ticket_reader")
    graph.add_edge("ticket_reader", "customer_context_reader")
    graph.add_edge("customer_context_reader", "knowledge_searcher")
    graph.add_edge("knowledge_searcher", "evidence_auditor")
    graph.add_edge("evidence_auditor", END)
    return graph.compile()


def create_ticket_reader_node(
    tool_runtime: SupportEscalationToolRuntime,
) -> Callable[[SupportEscalationState], Awaitable[SupportEscalationState]]:
    async def ticket_reader_node(state: SupportEscalationState) -> SupportEscalationState:
        input_payload = {"ticket_id": state["ticket_id"], "include_messages": True}
        authorization = await authorize_and_execute_read(
            state=state,
            tool_runtime=tool_runtime,
            tool_id="support_ticket_read",
            input_payload=input_payload,
        )
        ticket = authorization["output_payload"].get("ticket")
        if not isinstance(ticket, dict):
            raise SupportEscalationGraphError("Support output must include ticket object.")
        return {
            "ticket": cast(dict[str, Any], ticket),
            "ticket_tool_call_ids": [authorization["tool_call_id"]],
            "ticket_policy_decision_ids": authorization["policy_decision_ids"],
        }

    return ticket_reader_node


def create_customer_context_reader_node(
    tool_runtime: SupportEscalationToolRuntime,
) -> Callable[[SupportEscalationState], Awaitable[SupportEscalationState]]:
    async def customer_context_reader_node(
        state: SupportEscalationState,
    ) -> SupportEscalationState:
        customer_id = string_or_none(state.get("ticket", {}).get("customer_id"))
        if customer_id is None:
            raise SupportEscalationGraphError("Support ticket must include customer_id.")
        authorization = await authorize_and_execute_read(
            state=state,
            tool_runtime=tool_runtime,
            tool_id="crm_customer_profile_read",
            input_payload={"customer_id": customer_id},
        )
        customer = authorization["output_payload"].get("customer")
        if not isinstance(customer, dict):
            raise SupportEscalationGraphError("CRM output must include customer object.")
        return {
            "customer_profile": cast(dict[str, Any], customer),
            "customer_tool_call_ids": [authorization["tool_call_id"]],
            "customer_policy_decision_ids": authorization["policy_decision_ids"],
        }

    return customer_context_reader_node


def create_knowledge_searcher_node(
    tool_runtime: SupportEscalationToolRuntime,
) -> Callable[[SupportEscalationState], Awaitable[SupportEscalationState]]:
    async def knowledge_searcher_node(state: SupportEscalationState) -> SupportEscalationState:
        ticket = state.get("ticket", {})
        input_payload: dict[str, Any] = {
            "query": build_knowledge_query(ticket),
            "limit": 5,
        }
        if (product := string_or_none(ticket.get("product"))) is not None:
            input_payload["product"] = product
        if state.get("locale") is not None:
            input_payload["locale"] = state["locale"]
        authorization = await authorize_and_execute_read(
            state=state,
            tool_runtime=tool_runtime,
            tool_id="knowledge_base_search",
            input_payload=input_payload,
        )
        documents = authorization["output_payload"].get("documents", [])
        if not isinstance(documents, list):
            raise SupportEscalationGraphError("Knowledge output must include documents list.")
        return {
            "knowledge_documents": [
                document for document in documents if isinstance(document, dict)
            ],
            "knowledge_tool_call_ids": [authorization["tool_call_id"]],
            "knowledge_policy_decision_ids": authorization["policy_decision_ids"],
        }

    return knowledge_searcher_node


async def authorize_and_execute_read(
    *,
    state: SupportEscalationState,
    tool_runtime: SupportEscalationToolRuntime,
    tool_id: str,
    input_payload: dict[str, Any],
) -> dict[str, Any]:
    authorization = await tool_runtime.authorize_tool_call(
        ToolCallAuthorizationRequest(
            run_id=state["run_id"],
            workflow_id=CUSTOMER_SUPPORT_WORKFLOW_ID,
            tool_id=tool_id,
            autonomy_level=state["autonomy_level"],
            input_payload=input_payload,
            actor_id=state.get("actor_id"),
            trace_id=state.get("trace_id"),
        )
    )
    ensure_authorized(authorization)
    execution = await tool_runtime.execute_tool_call(
        authorization.id,
        ToolCallExecutionRequest(
            input_payload=input_payload,
            actor_id=state.get("actor_id"),
            trace_id=state.get("trace_id"),
        ),
    )
    policy_decision_ids: list[str] = []
    if authorization.policy_decision.decision_id is not None:
        policy_decision_ids.append(authorization.policy_decision.decision_id)
    return {
        "tool_call_id": str(authorization.id),
        "policy_decision_ids": policy_decision_ids,
        "output_payload": execution.output_payload,
    }


def evidence_auditor_node(state: SupportEscalationState) -> SupportEscalationState:
    evidence: list[dict[str, Any]] = []
    ticket = state.get("ticket", {})
    ticket_id = string_or_none(ticket.get("ticket_id")) or state["ticket_id"]
    evidence.append(
        {
            "kind": "support_ticket",
            "title": f"Support ticket {ticket_id}",
            "source_system": "support_system",
            "source_uri": string_or_none(ticket.get("source_uri")),
            "payload": ticket,
        }
    )
    customer = state.get("customer_profile", {})
    customer_id = string_or_none(customer.get("customer_id")) or "customer"
    evidence.append(
        {
            "kind": "crm_customer_profile",
            "title": f"CRM customer profile {customer_id}",
            "source_system": "crm",
            "source_uri": string_or_none(customer.get("source_uri")),
            "payload": customer,
        }
    )
    for document in state.get("knowledge_documents", []):
        document_id = string_or_none(document.get("document_id")) or "knowledge document"
        evidence.append(
            {
                "kind": "knowledge_base_document",
                "title": title_from_record(document, f"Knowledge document {document_id}"),
                "source_system": "knowledge_base",
                "source_uri": string_or_none(document.get("source_uri")),
                "payload": document,
            }
        )
    return {"evidence": evidence}


def ensure_authorized(authorization: ToolCallAuthorizationResponse) -> None:
    is_executable = (
        authorization.status == "pending"
        and authorization.execution_state == "authorized_not_executed"
    )
    if not is_executable:
        raise SupportEscalationGraphError(
            "Tool authorization did not return an executable tool call."
        )


def build_knowledge_query(ticket: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in ("subject", "product", "category", "priority"):
        if (value := string_or_none(ticket.get(key))) is not None:
            parts.append(value)
    tags = ticket.get("tags", [])
    if isinstance(tags, list):
        parts.extend(tag for tag in tags[:10] if isinstance(tag, str) and tag)
    if not parts:
        raise SupportEscalationGraphError(
            "Support ticket must include subject, product, category, priority, or tags."
        )
    return " | ".join(parts)


def collect_tool_call_ids(state: SupportEscalationState) -> list[str]:
    return [
        *state.get("ticket_tool_call_ids", []),
        *state.get("customer_tool_call_ids", []),
        *state.get("knowledge_tool_call_ids", []),
    ]


def collect_policy_decision_ids(state: SupportEscalationState) -> list[str]:
    raw_decisions = [
        *state.get("ticket_policy_decision_ids", []),
        *state.get("customer_policy_decision_ids", []),
        *state.get("knowledge_policy_decision_ids", []),
    ]
    return [decision for decision in raw_decisions if decision]


def title_from_record(record: dict[str, Any], fallback: str) -> str:
    for key in ("title", "subject", "document_id", "ticket_id"):
        value = record.get(key)
        if isinstance(value, str) and value:
            return value
    return fallback


def string_or_none(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def as_support_escalation_state(payload: object) -> SupportEscalationState:
    return cast(SupportEscalationState, payload)
