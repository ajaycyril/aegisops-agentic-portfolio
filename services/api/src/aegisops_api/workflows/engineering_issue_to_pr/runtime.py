from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
from typing import Any, Literal, cast
from urllib.parse import urlparse
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.orm import Session

from aegisops_api.audit import AuditEventInput, write_audit_event
from aegisops_api.db.models import EvidenceRecord, WorkflowRun, utc_now
from aegisops_api.tools import ToolPolicyEvaluator
from aegisops_api.tools.adapters import ToolAdapterRegistry
from aegisops_api.tools.registry import ToolRegistry
from aegisops_api.workflows.engineering_issue_to_pr.graph import (
    ENGINEERING_WORKFLOW_ID,
    IssueToPrGraphDependencies,
    IssueToPrGraphInput,
    IssueToPrState,
    IssueToPrToolRuntime,
    PolicyBackedIssueToPrToolRuntime,
    as_issue_to_pr_state,
    create_engineering_issue_to_pr_graph,
)
from aegisops_api.workflows.engineering_issue_to_pr.replay import load_issue_to_pr_replay_fixture
from aegisops_api.workflows.registry import WorkflowRegistry

IssueToPrRunStage = Literal["issue_context_collected"]


class IssueToPrRunRejectedError(RuntimeError):
    def __init__(self, reason_code: str, message: str, http_status: int = 409) -> None:
        super().__init__(message)
        self.reason_code = reason_code
        self.message = message
        self.http_status = http_status


class IssueToPrRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    repository: str | None = Field(default=None, min_length=1)
    issue_number: int | None = Field(default=None, gt=0)
    issue_url: str | None = Field(default=None, min_length=1)
    ref: str | None = Field(default=None, min_length=1)
    context_paths: list[str] | None = Field(default=None, max_length=10)
    actor_id: str | None = None
    trace_id: str | None = None

    @model_validator(mode="after")
    def validate_issue_locator(self) -> IssueToPrRunRequest:
        if self.issue_url is not None and (
            self.repository is not None or self.issue_number is not None
        ):
            raise ValueError("Use issue_url or repository plus issue_number, not both.")
        if (self.repository is None) != (self.issue_number is None):
            raise ValueError("repository and issue_number must be provided together.")
        return self


class EvidenceRecordSummary(BaseModel):
    id: UUID
    kind: str
    source_system: str
    source_uri: str | None
    title: str
    content_hash: str


class IssueToPrRunResponse(BaseModel):
    run_id: UUID
    workflow_id: str
    run_status: str
    stage: IssueToPrRunStage
    issue_title: str
    issue_url: str
    context_file_count: int
    tool_call_ids: list[str]
    evidence_records: list[EvidenceRecordSummary]
    policy_decision_ids: list[str]


async def collect_engineering_issue_context(
    run_id: UUID,
    request: IssueToPrRunRequest,
    session: Session,
    workflow_registry: WorkflowRegistry,
    tool_registry: ToolRegistry,
    policy_evaluator: ToolPolicyEvaluator,
    adapter_registry: ToolAdapterRegistry,
    available_connectors: set[str],
    tool_runtime: IssueToPrToolRuntime | None = None,
    replay_fixture_dir: Path | None = None,
) -> IssueToPrRunResponse:
    run = session.get(WorkflowRun, run_id)
    if run is None:
        raise IssueToPrRunRejectedError(
            reason_code="workflow_run_not_found",
            message="Workflow run was not found.",
            http_status=404,
        )
    ensure_run_can_collect_issue_context(run)

    try:
        run.status = "running"
        graph_state: IssueToPrState | None = None
        graph_input: IssueToPrGraphInput | None = None
        graph: Any | None = None
        if run.execution_mode == "replay":
            ensure_replay_request_does_not_override_fixture(request)
            graph_state = load_replay_graph_state(run, request, replay_fixture_dir)
            start_payload = {
                "stage": "issue_context_collection",
                "execution_mode": "replay",
                "replay_source_run_id": get_replay_source_run_id(run),
                "repository": graph_state["repository"],
                "issue_number": graph_state["issue_number"],
                "context_path_count": len(graph_state.get("context_paths", [])),
            }
        else:
            graph_input = build_graph_input_from_run(run, request)
            start_payload = {
                "stage": "issue_context_collection",
                "execution_mode": "live",
                "repository": graph_input.repository,
                "issue_number": graph_input.issue_number,
                "context_path_count": len(graph_input.context_paths),
            }
            runtime = tool_runtime or PolicyBackedIssueToPrToolRuntime(
                workflow_registry=workflow_registry,
                tool_registry=tool_registry,
                session=session,
                policy_evaluator=policy_evaluator,
                adapter_registry=adapter_registry,
                available_connectors=available_connectors,
            )
            graph = create_engineering_issue_to_pr_graph(
                IssueToPrGraphDependencies(tool_runtime=runtime)
            )

        write_audit_event(
            session,
            AuditEventInput(
                run_id=run.id,
                workflow_id=run.workflow_id,
                event_type="workflow_graph.started",
                actor_type="user" if request.actor_id else "system",
                actor_id=request.actor_id,
                action="workflow_graph.collect_issue_context",
                resource_type="workflow_run",
                resource_id=str(run.id),
                trace_id=request.trace_id,
                payload=start_payload,
            ),
        )
        session.flush()
        if graph_state is None:
            if graph is None or graph_input is None:
                raise IssueToPrRunRejectedError(
                    reason_code="workflow_graph_not_initialized",
                    message="Workflow graph was not initialized.",
                )
            graph_state = as_issue_to_pr_state(await graph.ainvoke(graph_input.to_initial_state()))
        evidence_records = persist_graph_evidence(session, run, graph_state)
        policy_decision_ids = collect_tool_policy_decision_ids(graph_state)
        write_audit_event(
            session,
            AuditEventInput(
                run_id=run.id,
                workflow_id=run.workflow_id,
                event_type="workflow_graph.evidence_collected",
                actor_type="user" if request.actor_id else "system",
                actor_id=request.actor_id,
                action="workflow_graph.collect_issue_context",
                resource_type="workflow_run",
                resource_id=str(run.id),
                trace_id=request.trace_id,
                payload={
                    "stage": "issue_context_collected",
                    "evidence_count": len(evidence_records),
                    "tool_call_count": len(graph_state.get("tool_call_ids", [])),
                    "policy_decision_ids": policy_decision_ids,
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
                action="workflow_graph.collect_issue_context",
                resource_type="workflow_run",
                resource_id=str(run.id),
                trace_id=request.trace_id,
                payload={"stage": "issue_context_collection", "error_type": type(exc).__name__},
            ),
        )
        session.commit()
        raise

    issue = graph_state["issue"]
    return IssueToPrRunResponse(
        run_id=run.id,
        workflow_id=run.workflow_id,
        run_status=run.status,
        stage="issue_context_collected",
        issue_title=str(issue["title"]),
        issue_url=str(issue["url"]),
        context_file_count=len(graph_state.get("context_files", [])),
        tool_call_ids=graph_state.get("tool_call_ids", []),
        evidence_records=[
            EvidenceRecordSummary(
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
    )


def ensure_run_can_collect_issue_context(run: WorkflowRun) -> None:
    if run.workflow_id != ENGINEERING_WORKFLOW_ID:
        raise IssueToPrRunRejectedError(
            reason_code="workflow_not_supported",
            message="This runtime path only supports engineering_issue_to_pr runs.",
        )
    if run.status not in {"queued", "running"}:
        raise IssueToPrRunRejectedError(
            reason_code="workflow_run_not_executable",
            message=f"Workflow run status is {run.status}.",
        )
    if run.execution_mode != "live":
        if run.execution_mode == "replay":
            if get_replay_source_run_id(run) is None:
                raise IssueToPrRunRejectedError(
                    reason_code="replay_source_required",
                    message="Replay mode requires replay_source_run_id from a captured real run.",
                    http_status=422,
                )
            return
        raise IssueToPrRunRejectedError(
            reason_code="execution_mode_not_supported",
            message=f"Workflow run execution mode is {run.execution_mode}.",
        )


def build_graph_input_from_run(
    run: WorkflowRun,
    request: IssueToPrRunRequest,
) -> IssueToPrGraphInput:
    payload = dict(run.input_payload or {})
    repository = request.repository
    issue_number = request.issue_number
    issue_url = request.issue_url
    if issue_url is None and repository is None and issue_number is None:
        issue_url = string_or_none(payload.get("issue_url"))
    if issue_url is not None:
        repository, issue_number = parse_github_issue_url(issue_url)
    if repository is None:
        repository = string_or_none(payload.get("repository"))
    if issue_number is None:
        issue_number = positive_int_or_none(payload.get("issue_number"))
    if repository is None or issue_number is None:
        raise IssueToPrRunRejectedError(
            reason_code="issue_locator_missing",
            message="Provide issue_url or repository plus issue_number.",
            http_status=422,
        )

    context_paths = request.context_paths
    if context_paths is None:
        context_paths = string_list_or_empty(payload.get("context_paths"))
    return IssueToPrGraphInput(
        run_id=run.id,
        repository=repository,
        issue_number=issue_number,
        ref=request.ref or string_or_none(payload.get("ref")) or "main",
        context_paths=context_paths,
        autonomy_level=cast(Any, run.autonomy_level),
        actor_id=request.actor_id or string_or_none(payload.get("actor_id")),
        trace_id=request.trace_id or string_or_none(payload.get("trace_id")),
    )


def load_replay_graph_state(
    run: WorkflowRun,
    request: IssueToPrRunRequest,
    replay_fixture_dir: Path | None,
) -> IssueToPrState:
    source_run_id = get_replay_source_run_id(run)
    if source_run_id is None:
        raise IssueToPrRunRejectedError(
            reason_code="replay_source_required",
            message="Replay mode requires replay_source_run_id from a captured real run.",
            http_status=422,
        )
    fixture = load_issue_to_pr_replay_fixture(source_run_id, replay_fixture_dir)
    return fixture.to_graph_state(
        run_id=run.id,
        autonomy_level=cast(Any, run.autonomy_level),
        actor_id=request.actor_id,
        trace_id=request.trace_id,
    )


def get_replay_source_run_id(run: WorkflowRun) -> str | None:
    payload = run.input_payload or {}
    return string_or_none(payload.get("replay_source_run_id"))


def ensure_replay_request_does_not_override_fixture(request: IssueToPrRunRequest) -> None:
    if any(
        value is not None
        for value in (
            request.repository,
            request.issue_number,
            request.issue_url,
            request.ref,
            request.context_paths,
        )
    ):
        raise IssueToPrRunRejectedError(
            reason_code="replay_input_override_not_allowed",
            message="Replay evidence collection must use the captured replay fixture inputs.",
            http_status=422,
        )


def parse_github_issue_url(issue_url: str) -> tuple[str, int]:
    parsed = urlparse(issue_url)
    if parsed.scheme not in {"http", "https"} or parsed.netloc != "github.com":
        raise IssueToPrRunRejectedError(
            reason_code="github_issue_url_invalid",
            message="GitHub issue URL must use https://github.com/{owner}/{repo}/issues/{number}.",
            http_status=422,
        )
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) != 4 or parts[2] != "issues":
        raise IssueToPrRunRejectedError(
            reason_code="github_issue_url_invalid",
            message="GitHub issue URL must use https://github.com/{owner}/{repo}/issues/{number}.",
            http_status=422,
        )
    try:
        issue_number = int(parts[3])
    except ValueError as exc:
        raise IssueToPrRunRejectedError(
            reason_code="github_issue_url_invalid",
            message="GitHub issue URL issue number must be a positive integer.",
            http_status=422,
        ) from exc
    if issue_number <= 0:
        raise IssueToPrRunRejectedError(
            reason_code="github_issue_url_invalid",
            message="GitHub issue URL issue number must be a positive integer.",
            http_status=422,
        )
    return f"{parts[0]}/{parts[1]}", issue_number


def persist_graph_evidence(
    session: Session,
    run: WorkflowRun,
    graph_state: IssueToPrState,
) -> list[EvidenceRecord]:
    issue = graph_state["issue"]
    captured_at = utc_now()
    records = [
        EvidenceRecord(
            id=uuid4(),
            run_id=run.id,
            workflow_id=run.workflow_id,
            kind="api_response",
            source_system="github",
            source_uri=str(issue["url"]),
            title=str(issue["title"]),
            content_hash=hash_mapping(issue),
            evidence_metadata={
                "evidence_kind": "github_issue",
                "labels": issue.get("labels", []),
                "author": issue.get("author"),
            },
            captured_at=captured_at,
        )
    ]
    for file_payload in graph_state.get("context_files", []):
        file_record = file_payload
        records.append(
            EvidenceRecord(
                id=uuid4(),
                run_id=run.id,
                workflow_id=run.workflow_id,
                kind="code",
                source_system="github",
                source_uri=build_github_blob_uri(
                    repository=str(graph_state["repository"]),
                    ref=str(file_record["ref"]),
                    path=str(file_record["path"]),
                ),
                title=str(file_record["path"]),
                content_hash=hash_mapping(
                    {
                        "path": file_record["path"],
                        "ref": file_record["ref"],
                        "sha": file_record["sha"],
                        "content": file_record["content"],
                    }
                ),
                evidence_metadata={
                    "evidence_kind": "github_file",
                    "path": file_record["path"],
                    "ref": file_record["ref"],
                    "sha": file_record["sha"],
                    "byte_count": len(str(file_record["content"]).encode("utf-8")),
                },
                captured_at=captured_at,
            )
        )
    for record in records:
        session.add(record)
    session.flush()
    return records


def collect_tool_policy_decision_ids(graph_state: IssueToPrState) -> list[str]:
    raw_decisions = graph_state.get("policy_decision_ids", [])
    return [decision for decision in raw_decisions if isinstance(decision, str) and decision]


def string_or_none(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def positive_int_or_none(value: object) -> int | None:
    if isinstance(value, int) and value > 0:
        return value
    return None


def string_list_or_empty(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item]


def build_github_blob_uri(repository: str, ref: str, path: str) -> str:
    clean_path = "/".join(part for part in path.split("/") if part)
    return f"https://github.com/{repository}/blob/{ref}/{clean_path}"


def hash_mapping(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256(encoded).hexdigest()
