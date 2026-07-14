from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Protocol, TypedDict, cast
from uuid import UUID

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.orm import Session

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

ENGINEERING_WORKFLOW_ID = "engineering_issue_to_pr"


class IssueToPrGraphError(RuntimeError):
    pass


class IssueToPrGraphInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: UUID
    repository: str = Field(min_length=1)
    issue_number: int = Field(gt=0)
    ref: str = Field(default="main", min_length=1)
    context_paths: list[str] = Field(default_factory=list, max_length=10)
    autonomy_level: AutonomyLevel = "draft_only"
    actor_id: str | None = None
    trace_id: str | None = None

    @model_validator(mode="after")
    def validate_context_paths(self) -> IssueToPrGraphInput:
        for path in self.context_paths:
            path_parts = path.split("/")
            if (
                not path
                or path.startswith("/")
                or any(part in {"", ".", ".."} for part in path_parts)
            ):
                raise ValueError("context paths must be relative repository file paths")
        return self

    def to_initial_state(self) -> IssueToPrState:
        return {
            "run_id": self.run_id,
            "workflow_id": ENGINEERING_WORKFLOW_ID,
            "repository": self.repository,
            "issue_number": self.issue_number,
            "ref": self.ref,
            "context_paths": self.context_paths,
            "autonomy_level": self.autonomy_level,
            "actor_id": self.actor_id,
            "trace_id": self.trace_id,
            "tool_call_ids": [],
            "context_files": [],
            "evidence": [],
        }


class IssueToPrState(TypedDict, total=False):
    run_id: UUID
    workflow_id: str
    repository: str
    issue_number: int
    ref: str
    context_paths: list[str]
    autonomy_level: AutonomyLevel
    actor_id: str | None
    trace_id: str | None
    issue: dict[str, Any]
    context_files: list[dict[str, Any]]
    tool_call_ids: list[str]
    evidence: list[dict[str, Any]]


class IssueToPrToolRuntime(Protocol):
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
class PolicyBackedIssueToPrToolRuntime:
    workflow_registry: WorkflowRegistry
    tool_registry: ToolRegistry
    session: Session
    policy_evaluator: ToolPolicyEvaluator
    adapter_registry: ToolAdapterRegistry
    available_connectors: set[str]

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
        )


@dataclass(frozen=True)
class IssueToPrGraphDependencies:
    tool_runtime: IssueToPrToolRuntime


def create_engineering_issue_to_pr_graph(dependencies: IssueToPrGraphDependencies) -> Any:
    read_issue = create_read_issue_node(dependencies.tool_runtime)
    read_context_files = create_read_context_files_node(dependencies.tool_runtime)

    graph = StateGraph(IssueToPrState)
    graph.add_node("read_issue", cast(Any, read_issue))
    graph.add_node("read_context_files", cast(Any, read_context_files))
    graph.add_node("assemble_evidence", cast(Any, assemble_evidence_node))
    graph.add_edge(START, "read_issue")
    graph.add_edge("read_issue", "read_context_files")
    graph.add_edge("read_context_files", "assemble_evidence")
    graph.add_edge("assemble_evidence", END)
    return graph.compile()


def create_read_issue_node(
    tool_runtime: IssueToPrToolRuntime,
) -> Callable[[IssueToPrState], Awaitable[IssueToPrState]]:
    async def read_issue_node(state: IssueToPrState) -> IssueToPrState:
        input_payload = {
            "repository": state["repository"],
            "issue_number": state["issue_number"],
        }
        authorization = await tool_runtime.authorize_tool_call(
            ToolCallAuthorizationRequest(
                run_id=state["run_id"],
                workflow_id=ENGINEERING_WORKFLOW_ID,
                tool_id="github_issue_read",
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
        return {
            "issue": execution.output_payload,
            "tool_call_ids": [*state.get("tool_call_ids", []), str(authorization.id)],
        }

    return read_issue_node


def create_read_context_files_node(
    tool_runtime: IssueToPrToolRuntime,
) -> Callable[[IssueToPrState], Awaitable[IssueToPrState]]:
    async def read_context_files_node(state: IssueToPrState) -> IssueToPrState:
        context_files: list[dict[str, Any]] = []
        tool_call_ids = list(state.get("tool_call_ids", []))
        for path in state.get("context_paths", []):
            input_payload = {
                "repository": state["repository"],
                "path": path,
                "ref": state["ref"],
            }
            authorization = await tool_runtime.authorize_tool_call(
                ToolCallAuthorizationRequest(
                    run_id=state["run_id"],
                    workflow_id=ENGINEERING_WORKFLOW_ID,
                    tool_id="github_file_read",
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
            context_files.append(execution.output_payload)
            tool_call_ids.append(str(authorization.id))
        return {"context_files": context_files, "tool_call_ids": tool_call_ids}

    return read_context_files_node


def assemble_evidence_node(state: IssueToPrState) -> IssueToPrState:
    issue = state.get("issue")
    if issue is None:
        raise IssueToPrGraphError("Issue evidence is missing.")

    evidence: list[dict[str, Any]] = [
        {
            "kind": "github_issue",
            "title": issue["title"],
            "source_uri": issue["url"],
            "tool_call_id": state.get("tool_call_ids", [""])[0],
        }
    ]
    for file_payload in state.get("context_files", []):
        source_uri = build_github_blob_uri(
            repository=state["repository"],
            ref=state["ref"],
            path=str(file_payload["path"]),
        )
        evidence.append(
            {
                "kind": "github_file",
                "title": file_payload["path"],
                "source_uri": source_uri,
                "sha": file_payload["sha"],
            }
        )
    return {"evidence": evidence}


def ensure_authorized(authorization: ToolCallAuthorizationResponse) -> None:
    is_executable = (
        authorization.status == "pending"
        and authorization.execution_state == "authorized_not_executed"
    )
    if not is_executable:
        raise IssueToPrGraphError("Tool authorization did not return an executable tool call.")


def build_github_blob_uri(repository: str, ref: str, path: str) -> str:
    clean_path = "/".join(part for part in path.split("/") if part)
    return f"https://github.com/{repository}/blob/{ref}/{clean_path}"


def as_issue_to_pr_state(payload: object) -> IssueToPrState:
    return cast(IssueToPrState, payload)
