from __future__ import annotations

import json
from hashlib import sha256
from typing import Any, Literal, Protocol
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from aegisops_api.audit import AuditEventInput, write_audit_event
from aegisops_api.config import Settings, get_settings
from aegisops_api.db.models import WorkflowRegistrySnapshot, WorkflowRun
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
