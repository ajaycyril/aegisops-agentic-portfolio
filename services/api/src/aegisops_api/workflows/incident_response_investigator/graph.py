from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol, Self, TypedDict, cast
from uuid import UUID

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, ConfigDict, Field, model_validator
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

INCIDENT_WORKFLOW_ID = "incident_response_investigator"


class IncidentInvestigationGraphError(RuntimeError):
    pass


class IncidentTimeWindow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start: datetime
    end: datetime

    @model_validator(mode="after")
    def validate_window_order(self) -> Self:
        if self.end <= self.start:
            raise ValueError("incident time_window.end must be after time_window.start")
        return self

    def to_tool_payload(self) -> dict[str, str]:
        return {
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
        }


class IncidentInvestigationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: UUID
    incident_id: str = Field(min_length=1)
    service: str = Field(min_length=1)
    time_window: IncidentTimeWindow
    severity: str | None = Field(default=None, min_length=1)
    environment: str | None = Field(default=None, min_length=1)
    repository: str | None = Field(default=None, min_length=1)
    ref: str = Field(default="main", min_length=1)
    suspect_paths: list[str] = Field(default_factory=list, max_length=10)
    autonomy_level: AutonomyLevel = "read_only"
    actor_id: str | None = None
    trace_id: str | None = None

    @model_validator(mode="after")
    def validate_code_context(self) -> Self:
        if self.suspect_paths and self.repository is None:
            raise ValueError("repository is required when suspect_paths are provided")
        for path in self.suspect_paths:
            path_parts = path.split("/")
            if (
                not path
                or path.startswith("/")
                or any(part in {"", ".", ".."} for part in path_parts)
            ):
                raise ValueError("suspect_paths must be relative repository file paths")
        return self

    def to_initial_state(self) -> IncidentInvestigationState:
        return {
            "run_id": self.run_id,
            "workflow_id": INCIDENT_WORKFLOW_ID,
            "incident_id": self.incident_id,
            "service": self.service,
            "time_window": self.time_window.to_tool_payload(),
            "severity": self.severity,
            "environment": self.environment,
            "repository": self.repository,
            "ref": self.ref,
            "suspect_paths": self.suspect_paths,
            "autonomy_level": self.autonomy_level,
            "actor_id": self.actor_id,
            "trace_id": self.trace_id,
            "log_events": [],
            "deployment_events": [],
            "code_files": [],
            "log_tool_call_ids": [],
            "deployment_tool_call_ids": [],
            "code_tool_call_ids": [],
            "log_policy_decision_ids": [],
            "deployment_policy_decision_ids": [],
            "code_policy_decision_ids": [],
            "evidence": [],
        }


class IncidentInvestigationState(TypedDict, total=False):
    run_id: UUID
    workflow_id: str
    incident_id: str
    service: str
    time_window: dict[str, str]
    severity: str | None
    environment: str | None
    repository: str | None
    ref: str
    suspect_paths: list[str]
    autonomy_level: AutonomyLevel
    actor_id: str | None
    trace_id: str | None
    log_events: list[dict[str, Any]]
    deployment_events: list[dict[str, Any]]
    code_files: list[dict[str, Any]]
    log_tool_call_ids: list[str]
    deployment_tool_call_ids: list[str]
    code_tool_call_ids: list[str]
    log_policy_decision_ids: list[str]
    deployment_policy_decision_ids: list[str]
    code_policy_decision_ids: list[str]
    evidence: list[dict[str, Any]]


class IncidentInvestigationToolRuntime(Protocol):
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
class PolicyBackedIncidentToolRuntime:
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
class IncidentInvestigationGraphDependencies:
    tool_runtime: IncidentInvestigationToolRuntime


def create_incident_investigation_graph(
    dependencies: IncidentInvestigationGraphDependencies,
) -> Any:
    graph = StateGraph(IncidentInvestigationState)
    graph.add_node(
        "log_investigator",
        cast(Any, create_log_investigator_node(dependencies.tool_runtime)),
    )
    graph.add_node(
        "deployment_investigator",
        cast(Any, create_deployment_investigator_node(dependencies.tool_runtime)),
    )
    graph.add_node(
        "code_investigator",
        cast(Any, create_code_investigator_node(dependencies.tool_runtime)),
    )
    graph.add_node("evidence_auditor", cast(Any, evidence_auditor_node))
    graph.add_edge(START, "log_investigator")
    graph.add_edge("log_investigator", "deployment_investigator")
    graph.add_edge("deployment_investigator", "code_investigator")
    graph.add_edge("code_investigator", "evidence_auditor")
    graph.add_edge("evidence_auditor", END)
    return graph.compile()


def create_log_investigator_node(
    tool_runtime: IncidentInvestigationToolRuntime,
) -> Callable[[IncidentInvestigationState], Awaitable[IncidentInvestigationState]]:
    async def log_investigator_node(
        state: IncidentInvestigationState,
    ) -> IncidentInvestigationState:
        input_payload: dict[str, Any] = {
            "service": state["service"],
            "time_window": state["time_window"],
        }
        if state.get("severity") is not None:
            input_payload["severity"] = state["severity"]
        authorization = await authorize_and_execute_read(
            state=state,
            tool_runtime=tool_runtime,
            tool_id="observability_log_search",
            input_payload=input_payload,
        )
        output_payload = authorization["output_payload"]
        events = output_payload.get("events", [])
        if not isinstance(events, list):
            raise IncidentInvestigationGraphError("Observability output must include events list.")
        return {
            "log_events": [event for event in events if isinstance(event, dict)],
            "log_tool_call_ids": [authorization["tool_call_id"]],
            "log_policy_decision_ids": authorization["policy_decision_ids"],
        }

    return log_investigator_node


def create_deployment_investigator_node(
    tool_runtime: IncidentInvestigationToolRuntime,
) -> Callable[[IncidentInvestigationState], Awaitable[IncidentInvestigationState]]:
    async def deployment_investigator_node(
        state: IncidentInvestigationState,
    ) -> IncidentInvestigationState:
        input_payload: dict[str, Any] = {
            "service": state["service"],
            "time_window": state["time_window"],
        }
        if state.get("environment") is not None:
            input_payload["environment"] = state["environment"]
        authorization = await authorize_and_execute_read(
            state=state,
            tool_runtime=tool_runtime,
            tool_id="deployment_event_search",
            input_payload=input_payload,
        )
        output_payload = authorization["output_payload"]
        deployments = output_payload.get("deployments", [])
        if not isinstance(deployments, list):
            raise IncidentInvestigationGraphError(
                "Deployment output must include deployments list."
            )
        return {
            "deployment_events": [
                deployment for deployment in deployments if isinstance(deployment, dict)
            ],
            "deployment_tool_call_ids": [authorization["tool_call_id"]],
            "deployment_policy_decision_ids": authorization["policy_decision_ids"],
        }

    return deployment_investigator_node


def create_code_investigator_node(
    tool_runtime: IncidentInvestigationToolRuntime,
) -> Callable[[IncidentInvestigationState], Awaitable[IncidentInvestigationState]]:
    async def code_investigator_node(
        state: IncidentInvestigationState,
    ) -> IncidentInvestigationState:
        repository = state.get("repository")
        if repository is None or not state.get("suspect_paths"):
            return {
                "code_files": [],
                "code_tool_call_ids": [],
                "code_policy_decision_ids": [],
            }

        code_files: list[dict[str, Any]] = []
        tool_call_ids: list[str] = []
        policy_decision_ids: list[str] = []
        for path in state.get("suspect_paths", []):
            input_payload = {
                "repository": repository,
                "path": path,
                "ref": state["ref"],
            }
            authorization = await authorize_and_execute_read(
                state=state,
                tool_runtime=tool_runtime,
                tool_id="github_file_read",
                input_payload=input_payload,
            )
            code_files.append(authorization["output_payload"])
            tool_call_ids.append(authorization["tool_call_id"])
            policy_decision_ids.extend(authorization["policy_decision_ids"])
        return {
            "code_files": code_files,
            "code_tool_call_ids": tool_call_ids,
            "code_policy_decision_ids": policy_decision_ids,
        }

    return code_investigator_node


async def authorize_and_execute_read(
    *,
    state: IncidentInvestigationState,
    tool_runtime: IncidentInvestigationToolRuntime,
    tool_id: str,
    input_payload: dict[str, Any],
) -> dict[str, Any]:
    authorization = await tool_runtime.authorize_tool_call(
        ToolCallAuthorizationRequest(
            run_id=state["run_id"],
            workflow_id=INCIDENT_WORKFLOW_ID,
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


def evidence_auditor_node(state: IncidentInvestigationState) -> IncidentInvestigationState:
    evidence: list[dict[str, Any]] = []
    for event in state.get("log_events", []):
        evidence.append(
            {
                "kind": "observability_log_event",
                "title": title_from_event(event, "Log event"),
                "source_system": "observability",
                "source_uri": string_or_none(event.get("source_uri")),
                "payload": event,
            }
        )
    for deployment in state.get("deployment_events", []):
        evidence.append(
            {
                "kind": "deployment_event",
                "title": title_from_event(deployment, "Deployment event"),
                "source_system": "deployments",
                "source_uri": string_or_none(deployment.get("source_uri")),
                "payload": deployment,
            }
        )
    for file_payload in state.get("code_files", []):
        repository = state.get("repository")
        if repository is None:
            raise IncidentInvestigationGraphError("Repository is required for code evidence.")
        evidence.append(
            {
                "kind": "github_file",
                "title": str(file_payload["path"]),
                "source_system": "github",
                "source_uri": build_github_blob_uri(
                    repository=repository,
                    ref=str(file_payload["ref"]),
                    path=str(file_payload["path"]),
                ),
                "payload": file_payload,
            }
        )
    return {"evidence": evidence}


def ensure_authorized(authorization: ToolCallAuthorizationResponse) -> None:
    is_executable = (
        authorization.status == "pending"
        and authorization.execution_state == "authorized_not_executed"
    )
    if not is_executable:
        raise IncidentInvestigationGraphError(
            "Tool authorization did not return an executable tool call."
        )


def collect_tool_call_ids(state: IncidentInvestigationState) -> list[str]:
    return [
        *state.get("log_tool_call_ids", []),
        *state.get("deployment_tool_call_ids", []),
        *state.get("code_tool_call_ids", []),
    ]


def collect_policy_decision_ids(state: IncidentInvestigationState) -> list[str]:
    raw_decisions = [
        *state.get("log_policy_decision_ids", []),
        *state.get("deployment_policy_decision_ids", []),
        *state.get("code_policy_decision_ids", []),
    ]
    return [decision for decision in raw_decisions if decision]


def title_from_event(event: dict[str, Any], fallback: str) -> str:
    for key in ("title", "name", "event_id", "deployment_id", "trace_id"):
        value = event.get(key)
        if isinstance(value, str) and value:
            return value
    return fallback


def string_or_none(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def build_github_blob_uri(repository: str, ref: str, path: str) -> str:
    clean_path = "/".join(part for part in path.split("/") if part)
    return f"https://github.com/{repository}/blob/{ref}/{clean_path}"


def as_incident_investigation_state(payload: object) -> IncidentInvestigationState:
    return cast(IncidentInvestigationState, payload)
