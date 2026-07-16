from datetime import timedelta
from decimal import Decimal
from typing import Any, cast
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from aegisops_api.budget import (
    BudgetEnforcementError,
    build_budget_policy_input,
    enforce_run_budget,
)
from aegisops_api.db.models import AuditEvent, WorkflowRun, utc_now
from aegisops_api.policy import PolicyDecision


class ScalarResult:
    def __init__(self, value: object) -> None:
        self.value = value

    def scalar_one(self) -> object:
        return self.value


class BudgetSession:
    def __init__(self, tool_call_count: int, estimated_cost_usd: Decimal) -> None:
        self.query_results = [tool_call_count, estimated_cost_usd]
        self.execute_count = 0
        self.added: list[object] = []
        self.flush_count = 0
        self.commit_count = 0

    def execute(self, _statement: object) -> ScalarResult:
        result = self.query_results[self.execute_count]
        self.execute_count += 1
        return ScalarResult(result)

    def add(self, instance: object) -> None:
        self.added.append(instance)

    def flush(self) -> None:
        self.flush_count += 1

    def commit(self) -> None:
        self.commit_count += 1


class FakeBudgetPolicyEvaluator:
    def __init__(self, decision: PolicyDecision) -> None:
        self.decision = decision
        self.inputs: list[dict[str, Any]] = []

    async def evaluate(self, input_payload: dict[str, Any]) -> PolicyDecision:
        self.inputs.append(input_payload)
        return self.decision


def create_run() -> WorkflowRun:
    now = utc_now()
    return WorkflowRun(
        id=uuid4(),
        workflow_id="customer_support_escalation",
        registry_snapshot_id=uuid4(),
        status="running",
        execution_mode="live",
        autonomy_level="draft_only",
        input_payload={},
        budget={"max_estimated_usd": 1.0, "max_tool_calls": 3, "max_run_seconds": 300},
        policy_context={},
        started_at=now - timedelta(seconds=120),
        updated_at=now,
    )


def test_build_budget_policy_input_includes_persisted_and_requested_usage() -> None:
    run = create_run()
    session = BudgetSession(tool_call_count=2, estimated_cost_usd=Decimal("0.25"))

    policy_input = build_budget_policy_input(
        run=run,
        session=cast(Session, session),
        requested_tool_calls=1,
        requested_estimated_cost_usd=Decimal("0.10"),
        now=run.started_at + timedelta(seconds=120),
    )

    assert policy_input["budget"]["max_tool_calls"] == 3
    assert policy_input["tool_call_count"] == 3
    assert policy_input["estimated_cost_usd"] == 0.35
    assert policy_input["elapsed_seconds"] == 120
    assert policy_input["requested_tool_calls"] == 1


@pytest.mark.asyncio
async def test_enforce_run_budget_records_audit_and_fails_run_when_policy_blocks() -> None:
    run = create_run()
    session = BudgetSession(tool_call_count=3, estimated_cost_usd=Decimal("0.25"))
    evaluator = FakeBudgetPolicyEvaluator(
        PolicyDecision(
            package_path="aegisops.budget",
            allowed=False,
            requires_approval=True,
            decision_id="budget-decision-1",
            reason_codes=["tool_call_limit_exceeded"],
            result={
                "allow": False,
                "requires_approval": True,
                "reason_codes": ["tool_call_limit_exceeded"],
            },
        )
    )

    with pytest.raises(BudgetEnforcementError) as exc_info:
        await enforce_run_budget(
            run=run,
            session=cast(Session, session),
            budget_evaluator=evaluator,
            requested_tool_calls=1,
            action="tool_call.authorize",
            actor_id="reviewer-123",
            trace_id="trace-budget",
        )

    assert exc_info.value.reason_code == "tool_call_limit_exceeded"
    assert run.status == "failed"
    assert run.failure_reason == "Run budget exceeded: tool_call_limit_exceeded"
    assert evaluator.inputs[0]["tool_call_count"] == 4
    assert session.commit_count == 1
    audit_event = next(item for item in session.added if isinstance(item, AuditEvent))
    assert audit_event.event_type == "budget.blocked"
    assert audit_event.policy_decision_id == "budget-decision-1"
    assert audit_event.payload["requested_tool_calls"] == 1
