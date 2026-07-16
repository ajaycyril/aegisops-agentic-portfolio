from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Protocol
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from aegisops_api.audit import AuditEventInput, write_audit_event
from aegisops_api.db.models import ModelCall, ToolCall, WorkflowRun, utc_now
from aegisops_api.policy import OpaClient, PolicyDecision
from aegisops_api.workflows.runs import BudgetEnvelope


class BudgetEnforcementError(RuntimeError):
    def __init__(
        self,
        reason_code: str,
        message: str,
        http_status: int = 429,
        policy_decision: PolicyDecision | None = None,
    ) -> None:
        super().__init__(message)
        self.reason_code = reason_code
        self.message = message
        self.http_status = http_status
        self.policy_decision = policy_decision


class BudgetPolicyEvaluator(Protocol):
    async def evaluate(self, input_payload: dict[str, Any]) -> PolicyDecision:
        pass


class OpaBudgetPolicyEvaluator:
    def __init__(self, opa_client: OpaClient) -> None:
        self._opa_client = opa_client

    async def evaluate(self, input_payload: dict[str, Any]) -> PolicyDecision:
        return await self._opa_client.evaluate("aegisops.budget", input_payload)


async def enforce_run_budget(
    *,
    run: WorkflowRun,
    session: Session,
    budget_evaluator: BudgetPolicyEvaluator | None,
    requested_tool_calls: int = 0,
    requested_estimated_cost_usd: Decimal = Decimal("0"),
    action: str,
    actor_id: str | None = None,
    trace_id: str | None = None,
) -> PolicyDecision | None:
    if budget_evaluator is None:
        return None

    policy_input = build_budget_policy_input(
        run=run,
        session=session,
        requested_tool_calls=requested_tool_calls,
        requested_estimated_cost_usd=requested_estimated_cost_usd,
    )
    decision = await budget_evaluator.evaluate(policy_input)
    if decision.allowed:
        return decision

    reason_code = decision.reason_codes[0] if decision.reason_codes else "run_budget_exceeded"
    run.status = "failed"
    run.failure_reason = f"Run budget exceeded: {reason_code}"
    write_audit_event(
        session,
        AuditEventInput(
            run_id=run.id,
            workflow_id=run.workflow_id,
            event_type="budget.blocked",
            actor_type="user" if actor_id else "system",
            actor_id=actor_id,
            action=action,
            resource_type="workflow_run",
            resource_id=str(run.id),
            policy_decision_id=decision.decision_id,
            trace_id=trace_id,
            payload={
                "reason_codes": decision.reason_codes,
                "requires_approval": decision.requires_approval,
                "budget": policy_input["budget"],
                "estimated_cost_usd": policy_input["estimated_cost_usd"],
                "tool_call_count": policy_input["tool_call_count"],
                "elapsed_seconds": policy_input["elapsed_seconds"],
                "requested_tool_calls": requested_tool_calls,
                "requested_estimated_cost_usd": str(requested_estimated_cost_usd),
            },
        ),
    )
    session.commit()
    raise BudgetEnforcementError(
        reason_code=reason_code,
        message="Workflow run budget was exceeded before this action could continue.",
        policy_decision=decision,
    )


def build_budget_policy_input(
    *,
    run: WorkflowRun,
    session: Session,
    requested_tool_calls: int = 0,
    requested_estimated_cost_usd: Decimal = Decimal("0"),
    now: datetime | None = None,
) -> dict[str, Any]:
    budget = parse_run_budget(run)
    current_tool_call_count = count_run_tool_calls(session, run.id)
    current_estimated_cost_usd = sum_run_model_cost(session, run.id)
    elapsed_seconds = calculate_elapsed_seconds(run, now=now)
    estimated_cost_usd = current_estimated_cost_usd + requested_estimated_cost_usd

    return {
        "run_id": str(run.id),
        "workflow_id": run.workflow_id,
        "execution_mode": run.execution_mode,
        "run_status": run.status,
        "budget": budget.model_dump(mode="json"),
        "estimated_cost_usd": float(estimated_cost_usd),
        "tool_call_count": current_tool_call_count + requested_tool_calls,
        "elapsed_seconds": elapsed_seconds,
        "requested_tool_calls": requested_tool_calls,
        "requested_estimated_cost_usd": float(requested_estimated_cost_usd),
    }


def parse_run_budget(run: WorkflowRun) -> BudgetEnvelope:
    try:
        return BudgetEnvelope.model_validate(run.budget)
    except ValidationError as exc:
        raise BudgetEnforcementError(
            reason_code="run_budget_invalid",
            message="Workflow run has an invalid budget envelope.",
            http_status=500,
        ) from exc


def count_run_tool_calls(session: Session, run_id: UUID) -> int:
    value = session.execute(
        select(func.count(ToolCall.id)).where(ToolCall.run_id == run_id),
    ).scalar_one()
    return int(value or 0)


def sum_run_model_cost(session: Session, run_id: UUID) -> Decimal:
    value = session.execute(
        select(func.coalesce(func.sum(ModelCall.estimated_cost_usd), 0)).where(
            ModelCall.run_id == run_id,
        ),
    ).scalar_one()
    return Decimal(str(value or 0))


def calculate_elapsed_seconds(run: WorkflowRun, now: datetime | None = None) -> int:
    started_at = run.started_at
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=UTC)
    resolved_now = now or utc_now()
    if resolved_now.tzinfo is None:
        resolved_now = resolved_now.replace(tzinfo=UTC)
    return max(0, int((resolved_now - started_at).total_seconds()))
