from __future__ import annotations

import json
from collections.abc import Mapping
from hashlib import sha256
from pathlib import Path
from typing import Any, Literal, cast
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.orm import Session

from aegisops_api.audit import AuditEventInput, write_audit_event
from aegisops_api.db.models import EvidenceRecord, WorkflowRun, utc_now
from aegisops_api.tools import ToolPolicyEvaluator
from aegisops_api.tools.adapters import ToolAdapterRegistry
from aegisops_api.tools.registry import ToolRegistry
from aegisops_api.workflows.incident_response_investigator.graph import (
    INCIDENT_WORKFLOW_ID,
    IncidentInvestigationGraphDependencies,
    IncidentInvestigationInput,
    IncidentInvestigationState,
    IncidentInvestigationToolRuntime,
    IncidentTimeWindow,
    PolicyBackedIncidentToolRuntime,
    as_incident_investigation_state,
    collect_policy_decision_ids,
    collect_tool_call_ids,
    create_incident_investigation_graph,
    evidence_auditor_node,
)
from aegisops_api.workflows.incident_response_investigator.replay import (
    load_incident_replay_fixture,
)
from aegisops_api.workflows.registry import WorkflowRegistry

IncidentRunStage = Literal["incident_evidence_collected"]


class IncidentInvestigationRejectedError(RuntimeError):
    def __init__(self, reason_code: str, message: str, http_status: int = 409) -> None:
        super().__init__(message)
        self.reason_code = reason_code
        self.message = message
        self.http_status = http_status


class IncidentInvestigationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    incident_id: str | None = Field(default=None, min_length=1)
    service: str | None = Field(default=None, min_length=1)
    time_window: IncidentTimeWindow | None = None
    severity: str | None = Field(default=None, min_length=1)
    environment: str | None = Field(default=None, min_length=1)
    repository: str | None = Field(default=None, min_length=1)
    ref: str | None = Field(default=None, min_length=1)
    suspect_paths: list[str] | None = Field(default=None, max_length=10)
    actor_id: str | None = None
    trace_id: str | None = None
    include_rca: bool = False

    @model_validator(mode="after")
    def validate_rca_not_enabled(self) -> IncidentInvestigationRequest:
        if self.include_rca:
            raise ValueError(
                "RCA generation is not enabled until evidence validation and approval gates exist."
            )
        return self


class IncidentEvidenceRecordSummary(BaseModel):
    id: UUID
    kind: str
    source_system: str
    source_uri: str | None
    title: str
    content_hash: str


class IncidentInvestigationResponse(BaseModel):
    run_id: UUID
    workflow_id: str
    run_status: str
    stage: IncidentRunStage
    incident_id: str
    service: str
    log_event_count: int
    deployment_event_count: int
    code_file_count: int
    tool_call_ids: list[str]
    evidence_records: list[IncidentEvidenceRecordSummary]
    policy_decision_ids: list[str]
    rca_generation_enabled: Literal[False] = False
    write_actions_enabled: Literal[False] = False


async def collect_incident_evidence(
    run_id: UUID,
    request: IncidentInvestigationRequest,
    session: Session,
    workflow_registry: WorkflowRegistry,
    tool_registry: ToolRegistry,
    policy_evaluator: ToolPolicyEvaluator,
    adapter_registry: ToolAdapterRegistry,
    available_connectors: set[str],
    tool_runtime: IncidentInvestigationToolRuntime | None = None,
    replay_fixture_dir: Path | None = None,
) -> IncidentInvestigationResponse:
    run = session.get(WorkflowRun, run_id)
    if run is None:
        raise IncidentInvestigationRejectedError(
            reason_code="workflow_run_not_found",
            message="Workflow run was not found.",
            http_status=404,
        )
    ensure_run_can_collect_incident_evidence(run)

    graph_state: IncidentInvestigationState | None = None
    graph_input: IncidentInvestigationInput | None = None
    try:
        run.status = "running"
        if run.execution_mode == "replay":
            ensure_replay_request_does_not_override_fixture(request)
            graph_state = load_replay_graph_state(run, request, replay_fixture_dir)
            start_payload = {
                "stage": "incident_evidence_collection",
                "execution_mode": "replay",
                "replay_source_run_id": get_replay_source_run_id(run),
                "incident_id": graph_state["incident_id"],
                "service": graph_state["service"],
                "suspect_path_count": len(graph_state.get("suspect_paths", [])),
                "rca_generation_enabled": False,
                "write_actions_enabled": False,
            }
        else:
            graph_input = build_graph_input_from_run(run, request)
            start_payload = {
                "stage": "incident_evidence_collection",
                "execution_mode": "live",
                "incident_id": graph_input.incident_id,
                "service": graph_input.service,
                "suspect_path_count": len(graph_input.suspect_paths),
                "rca_generation_enabled": False,
                "write_actions_enabled": False,
            }
        write_audit_event(
            session,
            AuditEventInput(
                run_id=run.id,
                workflow_id=run.workflow_id,
                event_type="workflow_graph.started",
                actor_type="user" if request.actor_id else "system",
                actor_id=request.actor_id,
                action="workflow_graph.collect_incident_evidence",
                resource_type="workflow_run",
                resource_id=str(run.id),
                trace_id=request.trace_id,
                payload=start_payload,
            ),
        )
        session.flush()
        if graph_state is None:
            if graph_input is None:
                raise IncidentInvestigationRejectedError(
                    reason_code="workflow_graph_not_initialized",
                    message="Workflow graph was not initialized.",
                )
            runtime = tool_runtime or PolicyBackedIncidentToolRuntime(
                workflow_registry=workflow_registry,
                tool_registry=tool_registry,
                session=session,
                policy_evaluator=policy_evaluator,
                adapter_registry=adapter_registry,
                available_connectors=available_connectors,
            )
            graph = create_incident_investigation_graph(
                IncidentInvestigationGraphDependencies(tool_runtime=runtime)
            )
            graph_state = as_incident_investigation_state(
                await graph.ainvoke(graph_input.to_initial_state())
            )
        elif not graph_state.get("evidence"):
            graph_state.update(evidence_auditor_node(graph_state))
        evidence_records = persist_incident_evidence(session, run, graph_state)
        policy_decision_ids = collect_policy_decision_ids(graph_state)
        write_audit_event(
            session,
            AuditEventInput(
                run_id=run.id,
                workflow_id=run.workflow_id,
                event_type="workflow_graph.evidence_collected",
                actor_type="user" if request.actor_id else "system",
                actor_id=request.actor_id,
                action="workflow_graph.collect_incident_evidence",
                resource_type="workflow_run",
                resource_id=str(run.id),
                trace_id=request.trace_id,
                payload={
                    "stage": "incident_evidence_collected",
                    "evidence_count": len(evidence_records),
                    "tool_call_count": len(collect_tool_call_ids(graph_state)),
                    "policy_decision_ids": policy_decision_ids,
                    "rca_generation_enabled": False,
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
                action="workflow_graph.collect_incident_evidence",
                resource_type="workflow_run",
                resource_id=str(run.id),
                trace_id=request.trace_id,
                payload={
                    "stage": "incident_evidence_collection",
                    "error_type": type(exc).__name__,
                },
            ),
        )
        session.commit()
        raise

    return IncidentInvestigationResponse(
        run_id=run.id,
        workflow_id=run.workflow_id,
        run_status=run.status,
        stage="incident_evidence_collected",
        incident_id=graph_state["incident_id"],
        service=graph_state["service"],
        log_event_count=len(graph_state.get("log_events", [])),
        deployment_event_count=len(graph_state.get("deployment_events", [])),
        code_file_count=len(graph_state.get("code_files", [])),
        tool_call_ids=collect_tool_call_ids(graph_state),
        evidence_records=[
            IncidentEvidenceRecordSummary(
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


def ensure_run_can_collect_incident_evidence(run: WorkflowRun) -> None:
    if run.workflow_id != INCIDENT_WORKFLOW_ID:
        raise IncidentInvestigationRejectedError(
            reason_code="workflow_not_supported",
            message="This runtime path only supports incident_response_investigator runs.",
        )
    if run.status not in {"queued", "running"}:
        raise IncidentInvestigationRejectedError(
            reason_code="workflow_run_not_executable",
            message=f"Workflow run status is {run.status}.",
        )
    if run.execution_mode != "live":
        if run.execution_mode == "replay":
            if get_replay_source_run_id(run) is None:
                raise IncidentInvestigationRejectedError(
                    reason_code="replay_source_required",
                    message="Replay mode requires replay_source_run_id from a captured real run.",
                    http_status=422,
                )
            return
        raise IncidentInvestigationRejectedError(
            reason_code="execution_mode_not_supported",
            message=f"Workflow run execution mode is {run.execution_mode}.",
        )


def build_graph_input_from_run(
    run: WorkflowRun,
    request: IncidentInvestigationRequest,
) -> IncidentInvestigationInput:
    payload = run.input_payload or {}
    incident_id = request.incident_id or string_or_none(payload.get("incident_id"))
    service = request.service or string_or_none(payload.get("service"))
    time_window = request.time_window or time_window_or_none(payload.get("time_window"))
    if incident_id is None or service is None or time_window is None:
        raise IncidentInvestigationRejectedError(
            reason_code="incident_input_missing",
            message="Provide incident_id, service, and time_window.",
            http_status=422,
        )
    return IncidentInvestigationInput(
        run_id=run.id,
        incident_id=incident_id,
        service=service,
        time_window=time_window,
        severity=request.severity or string_or_none(payload.get("severity")),
        environment=request.environment or string_or_none(payload.get("environment")),
        repository=request.repository or string_or_none(payload.get("repository")),
        ref=request.ref or string_or_none(payload.get("ref")) or "main",
        suspect_paths=(
            request.suspect_paths
            if request.suspect_paths is not None
            else string_list_or_empty(payload.get("suspect_paths"))
        ),
        autonomy_level=cast(Any, run.autonomy_level),
        actor_id=request.actor_id or string_or_none(payload.get("actor_id")),
        trace_id=request.trace_id or string_or_none(payload.get("trace_id")),
    )


def load_replay_graph_state(
    run: WorkflowRun,
    request: IncidentInvestigationRequest,
    replay_fixture_dir: Path | None,
) -> IncidentInvestigationState:
    source_run_id = get_replay_source_run_id(run)
    if source_run_id is None:
        raise IncidentInvestigationRejectedError(
            reason_code="replay_source_required",
            message="Replay mode requires replay_source_run_id from a captured real run.",
            http_status=422,
        )
    fixture = load_incident_replay_fixture(source_run_id, replay_fixture_dir)
    return fixture.to_graph_state(
        run_id=run.id,
        autonomy_level=cast(Any, run.autonomy_level),
        actor_id=request.actor_id,
        trace_id=request.trace_id,
    )


def get_replay_source_run_id(run: WorkflowRun) -> str | None:
    payload = run.input_payload or {}
    return string_or_none(payload.get("replay_source_run_id"))


def ensure_replay_request_does_not_override_fixture(
    request: IncidentInvestigationRequest,
) -> None:
    if any(
        value is not None
        for value in (
            request.incident_id,
            request.service,
            request.time_window,
            request.severity,
            request.environment,
            request.repository,
            request.ref,
            request.suspect_paths,
        )
    ):
        raise IncidentInvestigationRejectedError(
            reason_code="replay_input_override_not_allowed",
            message="Replay evidence collection must use the captured replay fixture inputs.",
            http_status=422,
        )


def persist_incident_evidence(
    session: Session,
    run: WorkflowRun,
    graph_state: IncidentInvestigationState,
) -> list[EvidenceRecord]:
    captured_at = utc_now()
    records: list[EvidenceRecord] = []
    for evidence in graph_state.get("evidence", []):
        payload = mapping_or_empty(evidence.get("payload"))
        evidence_kind = str(evidence["kind"])
        records.append(
            EvidenceRecord(
                id=uuid4(),
                run_id=run.id,
                workflow_id=run.workflow_id,
                kind=evidence_record_kind(evidence_kind),
                source_system=str(evidence["source_system"]),
                source_uri=string_or_none(evidence.get("source_uri")),
                title=str(evidence["title"]),
                content_hash=hash_mapping(payload),
                evidence_metadata=metadata_for_evidence(evidence_kind, payload),
                captured_at=captured_at,
            )
        )
    for record in records:
        session.add(record)
    session.flush()
    return records


def evidence_record_kind(evidence_kind: str) -> str:
    if evidence_kind == "observability_log_event":
        return "log"
    if evidence_kind == "deployment_event":
        return "api_response"
    if evidence_kind == "github_file":
        return "code"
    return "api_response"


def metadata_for_evidence(evidence_kind: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    if evidence_kind == "observability_log_event":
        metadata = copy_selected_metadata(
            payload,
            ("event_id", "timestamp", "severity", "service", "trace_id", "source_uri"),
        )
        metadata["evidence_kind"] = evidence_kind
        return metadata
    if evidence_kind == "deployment_event":
        metadata = copy_selected_metadata(
            payload,
            (
                "deployment_id",
                "environment",
                "deployed_at",
                "status",
                "version",
                "commit_sha",
                "source_uri",
            ),
        )
        metadata["evidence_kind"] = evidence_kind
        return metadata
    if evidence_kind == "github_file":
        metadata = copy_selected_metadata(payload, ("path", "ref", "sha"))
        content = payload.get("content")
        if isinstance(content, str):
            metadata["byte_count"] = len(content.encode("utf-8"))
        metadata["evidence_kind"] = evidence_kind
        return metadata
    return {}


def copy_selected_metadata(payload: Mapping[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
    return {key: payload[key] for key in keys if key in payload}


def time_window_or_none(value: object) -> IncidentTimeWindow | None:
    if not isinstance(value, dict):
        return None
    return IncidentTimeWindow.model_validate(value)


def mapping_or_empty(value: object) -> Mapping[str, Any]:
    return cast(Mapping[str, Any], value) if isinstance(value, dict) else {}


def string_or_none(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def string_list_or_empty(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item]


def hash_mapping(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256(encoded).hexdigest()
