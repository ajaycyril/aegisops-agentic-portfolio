from __future__ import annotations

import json
from hashlib import sha256
from typing import Any, Literal, Protocol, cast
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from aegisops_api.audit import AuditEventInput, write_audit_event
from aegisops_api.config import Settings, get_settings
from aegisops_api.db.models import (
    Approval,
    AuditEvent,
    EvidenceRecord,
    MemoryRecord,
    ModelCall,
    ToolCall,
    WorkflowRegistrySnapshot,
    WorkflowRun,
)
from aegisops_api.policy import OpaClient, PolicyDecision
from aegisops_api.workflows.registry import AutonomyLevel, WorkflowDetail, WorkflowRegistry

ExecutionMode = Literal["replay", "live"]
WorkflowRunStatus = Literal[
    "queued",
    "running",
    "waiting_for_approval",
    "completed",
    "failed",
    "canceled",
]


class WorkflowRunStartRejectedError(RuntimeError):
    def __init__(self, reason_code: str, message: str, http_status: int = 409) -> None:
        super().__init__(message)
        self.reason_code = reason_code
        self.message = message
        self.http_status = http_status


class BudgetEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_estimated_usd: float = Field(gt=0)
    max_tool_calls: int = Field(gt=0)
    max_run_seconds: int = Field(gt=0)

    @classmethod
    def from_settings(cls, settings: Settings) -> BudgetEnvelope:
        return cls(
            max_estimated_usd=settings.max_agent_estimated_usd,
            max_tool_calls=settings.max_agent_tool_calls,
            max_run_seconds=settings.max_agent_run_seconds,
        )


class WorkflowRunStartRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    workflow_id: str
    execution_mode: ExecutionMode = "replay"
    autonomy_level: AutonomyLevel | None = None
    org_id: str | None = None
    user_id: str | None = None
    replay_source_run_id: str | None = None
    input_payload: dict[str, Any] = Field(default_factory=dict)
    budget: BudgetEnvelope | None = None


class PolicyDecisionSummary(BaseModel):
    allowed: bool
    requires_approval: bool
    decision_id: str | None
    reason_codes: list[str]


class WorkflowRunStartResponse(BaseModel):
    id: UUID
    workflow_id: str
    status: WorkflowRunStatus
    execution_mode: ExecutionMode
    autonomy_level: AutonomyLevel
    registry_snapshot_id: UUID
    budget: BudgetEnvelope
    policy_decision: PolicyDecisionSummary


class WorkflowRunTraceRecord(BaseModel):
    id: UUID
    workflow_id: str
    status: WorkflowRunStatus
    execution_mode: ExecutionMode
    autonomy_level: AutonomyLevel
    org_id: str | None
    user_id: str | None
    started_at: str
    updated_at: str
    completed_at: str | None
    failure_reason: str | None


class ApprovalTraceRecord(BaseModel):
    id: UUID
    status: str
    risk_class: str
    requested_action: str
    requested_by: str
    approver_id: str | None
    policy_decision_id: str | None
    requested_at: str
    decided_at: str | None
    expires_at: str | None


class ToolCallTraceRecord(BaseModel):
    id: UUID
    approval_id: UUID | None
    tool_name: str
    risk_class: str
    status: str
    policy_decision_id: str | None
    trace_id: str | None
    output_hash: str | None
    latency_ms: int | None
    started_at: str
    completed_at: str | None
    error_message: str | None
    execution_state: str | None


class ModelCallTraceRecord(BaseModel):
    id: UUID
    provider: str
    model: str
    purpose: str
    prompt_version: str
    input_token_count: int
    output_token_count: int
    estimated_cost_usd: str
    latency_ms: int | None
    trace_id: str | None
    status: str
    started_at: str
    completed_at: str | None
    error_message: str | None


class EvidenceTraceRecord(BaseModel):
    id: UUID
    kind: str
    source_system: str
    source_uri: str | None
    title: str
    content_hash: str
    metadata: dict[str, Any]
    captured_at: str
    created_at: str


class MemoryTraceRecord(BaseModel):
    id: UUID
    scope: str
    subject_id: str | None
    memory_key: str
    memory_value: dict[str, Any]
    retention_class: str
    data_sensitivity: str
    source_evidence_id: UUID | None
    created_at: str
    expires_at: str | None


class AuditTraceRecord(BaseModel):
    id: UUID
    event_type: str
    actor_type: str
    actor_id: str | None
    action: str
    resource_type: str | None
    resource_id: str | None
    policy_decision_id: str | None
    trace_id: str | None
    data_sensitivity: str
    payload: dict[str, Any]
    created_at: str


class WorkflowRunTraceResponse(BaseModel):
    run: WorkflowRunTraceRecord
    approvals: list[ApprovalTraceRecord]
    tool_calls: list[ToolCallTraceRecord]
    model_calls: list[ModelCallTraceRecord]
    evidence_records: list[EvidenceTraceRecord]
    memory_records: list[MemoryTraceRecord]
    audit_events: list[AuditTraceRecord]


class RunPolicyEvaluator(Protocol):
    async def evaluate(self, input_payload: dict[str, Any]) -> PolicyDecision:
        pass


class OpaRunPolicyEvaluator:
    def __init__(self, opa_client: OpaClient) -> None:
        self._opa_client = opa_client

    async def evaluate(self, input_payload: dict[str, Any]) -> PolicyDecision:
        return await self._opa_client.evaluate("aegisops.run_eligibility", input_payload)


async def start_workflow_run(
    request: WorkflowRunStartRequest,
    registry: WorkflowRegistry,
    session: Session,
    policy_evaluator: RunPolicyEvaluator,
    available_connectors: set[str],
    settings: Settings | None = None,
) -> WorkflowRunStartResponse:
    resolved_settings = settings or get_settings()
    workflow = registry.get_workflow(request.workflow_id, available_connectors=available_connectors)
    ensure_workflow_can_start(request, workflow)

    budget = request.budget or BudgetEnvelope.from_settings(resolved_settings)
    autonomy_level = request.autonomy_level or workflow.default_autonomy
    policy_input = build_run_policy_input(
        request=request,
        workflow=workflow,
        budget=budget,
        autonomy_level=autonomy_level,
        settings=resolved_settings,
    )
    decision = await policy_evaluator.evaluate(policy_input)
    if not decision.allowed and not decision.requires_approval:
        raise WorkflowRunStartRejectedError(
            reason_code="policy_denied",
            message="OPA policy denied workflow run creation.",
            http_status=403,
        )

    run_status: WorkflowRunStatus = (
        "waiting_for_approval" if decision.requires_approval else "queued"
    )

    try:
        snapshot = get_or_create_registry_snapshot(session, workflow)
        run = WorkflowRun(
            id=uuid4(),
            workflow_id=workflow.id,
            registry_snapshot_id=snapshot.id,
            status=run_status,
            execution_mode=request.execution_mode,
            autonomy_level=autonomy_level,
            org_id=request.org_id,
            user_id=request.user_id,
            input_payload={
                **request.input_payload,
                "replay_source_run_id": request.replay_source_run_id,
            },
            budget=budget.model_dump(mode="json"),
            policy_context={
                "decision_id": decision.decision_id,
                "package_path": decision.package_path,
                "reason_codes": decision.reason_codes,
                "result": decision.result,
            },
        )
        session.add(run)
        session.flush()
        write_audit_event(
            session,
            AuditEventInput(
                run_id=run.id,
                workflow_id=workflow.id,
                event_type="workflow_run.created",
                actor_type="user" if request.user_id else "system",
                actor_id=request.user_id,
                action="workflow_run.create",
                resource_type="workflow_run",
                resource_id=str(run.id),
                policy_decision_id=decision.decision_id,
                payload={
                    "status": run_status,
                    "execution_mode": request.execution_mode,
                    "autonomy_level": autonomy_level,
                    "policy_reason_codes": decision.reason_codes,
                },
            ),
        )
        session.commit()
    except Exception:
        session.rollback()
        raise

    return WorkflowRunStartResponse(
        id=run.id,
        workflow_id=run.workflow_id,
        status=run_status,
        execution_mode=request.execution_mode,
        autonomy_level=autonomy_level,
        registry_snapshot_id=snapshot.id,
        budget=budget,
        policy_decision=PolicyDecisionSummary(
            allowed=decision.allowed,
            requires_approval=decision.requires_approval,
            decision_id=decision.decision_id,
            reason_codes=decision.reason_codes,
        ),
    )


def get_workflow_run_trace(run_id: UUID, session: Session) -> WorkflowRunTraceResponse:
    run = session.get(WorkflowRun, run_id)
    if run is None:
        raise WorkflowRunStartRejectedError(
            reason_code="workflow_run_not_found",
            message="Workflow run was not found.",
            http_status=404,
        )

    approvals = session.execute(
        select(Approval).where(Approval.run_id == run.id).order_by(Approval.requested_at)
    ).scalars()
    tool_calls = session.execute(
        select(ToolCall).where(ToolCall.run_id == run.id).order_by(ToolCall.started_at)
    ).scalars()
    model_calls = session.execute(
        select(ModelCall).where(ModelCall.run_id == run.id).order_by(ModelCall.started_at)
    ).scalars()
    evidence_records = session.execute(
        select(EvidenceRecord)
        .where(EvidenceRecord.run_id == run.id)
        .order_by(EvidenceRecord.created_at)
    ).scalars()
    memory_records = session.execute(
        select(MemoryRecord).where(MemoryRecord.run_id == run.id).order_by(MemoryRecord.created_at)
    ).scalars()
    audit_events = session.execute(
        select(AuditEvent).where(AuditEvent.run_id == run.id).order_by(AuditEvent.created_at)
    ).scalars()

    return WorkflowRunTraceResponse(
        run=workflow_run_to_trace_record(run),
        approvals=[approval_to_trace_record(record) for record in approvals],
        tool_calls=[tool_call_to_trace_record(record) for record in tool_calls],
        model_calls=[model_call_to_trace_record(record) for record in model_calls],
        evidence_records=[evidence_to_trace_record(record) for record in evidence_records],
        memory_records=[memory_to_trace_record(record) for record in memory_records],
        audit_events=[audit_to_trace_record(record) for record in audit_events],
    )


def ensure_workflow_can_start(request: WorkflowRunStartRequest, workflow: WorkflowDetail) -> None:
    if workflow.status != "ready":
        raise WorkflowRunStartRejectedError(
            reason_code="workflow_not_ready",
            message=f"Workflow status is {workflow.status}.",
        )
    if workflow.missing_connectors:
        raise WorkflowRunStartRejectedError(
            reason_code="connectors_not_configured",
            message="Required connectors are not configured.",
        )
    if request.execution_mode == "replay":
        if not workflow.data_policy.replay_allowed_from_real_runs:
            raise WorkflowRunStartRejectedError(
                reason_code="replay_not_allowed",
                message="Workflow does not allow replay mode.",
            )
        if request.replay_source_run_id is None:
            raise WorkflowRunStartRejectedError(
                reason_code="replay_source_required",
                message="Replay mode requires a captured real run source.",
            )


def build_run_policy_input(
    request: WorkflowRunStartRequest,
    workflow: WorkflowDetail,
    budget: BudgetEnvelope,
    autonomy_level: AutonomyLevel,
    settings: Settings,
) -> dict[str, Any]:
    return {
        "workflow": workflow.model_dump(mode="json"),
        "workflow_id": workflow.id,
        "execution_mode": request.execution_mode,
        "autonomy_level": autonomy_level,
        "missing_connectors": workflow.missing_connectors,
        "required_connectors": workflow.required_connectors,
        "budget": budget.model_dump(mode="json"),
        "estimated_cost_usd": 0,
        "tool_call_count": 0,
        "elapsed_seconds": 0,
        "replay_source_run_id": request.replay_source_run_id,
        "live_workflow_runs_enabled": settings.live_workflow_runs_enabled,
        "require_human_approval": settings.require_human_approval,
    }


def get_or_create_registry_snapshot(
    session: Session,
    workflow: WorkflowDetail,
) -> WorkflowRegistrySnapshot:
    config_payload = workflow.model_dump(mode="json")
    config_hash = hash_payload(config_payload)
    existing_snapshot = session.execute(
        select(WorkflowRegistrySnapshot).where(
            WorkflowRegistrySnapshot.workflow_id == workflow.id,
            WorkflowRegistrySnapshot.config_hash == config_hash,
        )
    ).scalar_one_or_none()
    if existing_snapshot is not None:
        return existing_snapshot

    snapshot = WorkflowRegistrySnapshot(
        id=uuid4(),
        workflow_id=workflow.id,
        version=f"config-{config_hash[:12]}",
        source_path=workflow.source_path,
        config_hash=config_hash,
        config=config_payload,
        is_active=True,
        created_by="workflow_registry",
    )
    session.add(snapshot)
    session.flush()
    return snapshot


def hash_payload(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256(encoded).hexdigest()


def workflow_run_to_trace_record(run: WorkflowRun) -> WorkflowRunTraceRecord:
    return WorkflowRunTraceRecord(
        id=run.id,
        workflow_id=run.workflow_id,
        status=cast(WorkflowRunStatus, run.status),
        execution_mode=cast(ExecutionMode, run.execution_mode),
        autonomy_level=cast(AutonomyLevel, run.autonomy_level),
        org_id=run.org_id,
        user_id=run.user_id,
        started_at=run.started_at.isoformat(),
        updated_at=run.updated_at.isoformat(),
        completed_at=run.completed_at.isoformat() if run.completed_at is not None else None,
        failure_reason=run.failure_reason,
    )


def approval_to_trace_record(approval: Approval) -> ApprovalTraceRecord:
    return ApprovalTraceRecord(
        id=approval.id,
        status=approval.status,
        risk_class=approval.risk_class,
        requested_action=approval.requested_action,
        requested_by=approval.requested_by,
        approver_id=approval.approver_id,
        policy_decision_id=approval.policy_decision_id,
        requested_at=approval.requested_at.isoformat(),
        decided_at=approval.decided_at.isoformat() if approval.decided_at is not None else None,
        expires_at=approval.expires_at.isoformat() if approval.expires_at is not None else None,
    )


def tool_call_to_trace_record(tool_call: ToolCall) -> ToolCallTraceRecord:
    metadata = tool_call.call_metadata or {}
    execution_state = metadata.get("execution_state")
    return ToolCallTraceRecord(
        id=tool_call.id,
        approval_id=tool_call.approval_id,
        tool_name=tool_call.tool_name,
        risk_class=tool_call.risk_class,
        status=tool_call.status,
        policy_decision_id=tool_call.policy_decision_id,
        trace_id=tool_call.trace_id,
        output_hash=tool_call.output_hash,
        latency_ms=tool_call.latency_ms,
        started_at=tool_call.started_at.isoformat(),
        completed_at=(
            tool_call.completed_at.isoformat() if tool_call.completed_at is not None else None
        ),
        error_message=tool_call.error_message,
        execution_state=execution_state if isinstance(execution_state, str) else None,
    )


def model_call_to_trace_record(model_call: ModelCall) -> ModelCallTraceRecord:
    return ModelCallTraceRecord(
        id=model_call.id,
        provider=model_call.provider,
        model=model_call.model,
        purpose=model_call.purpose,
        prompt_version=model_call.prompt_version,
        input_token_count=model_call.input_token_count,
        output_token_count=model_call.output_token_count,
        estimated_cost_usd=str(model_call.estimated_cost_usd),
        latency_ms=model_call.latency_ms,
        trace_id=model_call.trace_id,
        status=model_call.status,
        started_at=model_call.started_at.isoformat(),
        completed_at=(
            model_call.completed_at.isoformat() if model_call.completed_at is not None else None
        ),
        error_message=model_call.error_message,
    )


def evidence_to_trace_record(evidence: EvidenceRecord) -> EvidenceTraceRecord:
    return EvidenceTraceRecord(
        id=evidence.id,
        kind=evidence.kind,
        source_system=evidence.source_system,
        source_uri=evidence.source_uri,
        title=evidence.title,
        content_hash=evidence.content_hash,
        metadata=evidence.evidence_metadata,
        captured_at=evidence.captured_at.isoformat(),
        created_at=evidence.created_at.isoformat(),
    )


def memory_to_trace_record(memory: MemoryRecord) -> MemoryTraceRecord:
    return MemoryTraceRecord(
        id=memory.id,
        scope=memory.scope,
        subject_id=memory.subject_id,
        memory_key=memory.memory_key,
        memory_value=memory.memory_value,
        retention_class=memory.retention_class,
        data_sensitivity=memory.data_sensitivity,
        source_evidence_id=memory.source_evidence_id,
        created_at=memory.created_at.isoformat(),
        expires_at=memory.expires_at.isoformat() if memory.expires_at is not None else None,
    )


def audit_to_trace_record(audit_event: AuditEvent) -> AuditTraceRecord:
    return AuditTraceRecord(
        id=audit_event.id,
        event_type=audit_event.event_type,
        actor_type=audit_event.actor_type,
        actor_id=audit_event.actor_id,
        action=audit_event.action,
        resource_type=audit_event.resource_type,
        resource_id=audit_event.resource_id,
        policy_decision_id=audit_event.policy_decision_id,
        trace_id=audit_event.trace_id,
        data_sensitivity=audit_event.data_sensitivity,
        payload=audit_event.payload,
        created_at=audit_event.created_at.isoformat(),
    )
