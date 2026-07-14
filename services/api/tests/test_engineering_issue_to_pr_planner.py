from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy.orm import Session

from aegisops_api.db.models import ModelCall
from aegisops_api.workflows.engineering_issue_to_pr.graph import (
    IssueToPrEvaluation,
    IssueToPrProposal,
    IssueToPrState,
    PlannedFileChange,
)
from aegisops_api.workflows.engineering_issue_to_pr.graph import (
    TestPlanStep as PlanStep,
)
from aegisops_api.workflows.engineering_issue_to_pr.planner import (
    OpenAIIssueToPrPlanner,
    OpenAIPlannerConfig,
)


class PlannerSession:
    def __init__(self) -> None:
        self.added: list[object] = []
        self.flush_count = 0

    def add(self, instance: object) -> None:
        self.added.append(instance)

    def flush(self) -> None:
        self.flush_count += 1


class FakeResponses:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def parse(self, **kwargs: Any) -> object:
        self.calls.append(kwargs)
        text_format = kwargs["text_format"]
        if text_format is IssueToPrProposal:
            parsed: IssueToPrProposal | IssueToPrEvaluation = IssueToPrProposal(
                summary="Plan grounded in issue evidence.",
                problem_statement="CI fails during static analysis.",
                source_evidence_uris=["https://github.com/acme/app/issues/42"],
                planned_changes=[
                    PlannedFileChange(
                        path="src/service.py",
                        change_type="modify",
                        rationale="Address the failing behavior referenced by the issue.",
                        evidence_uris=["https://github.com/acme/app/issues/42"],
                    )
                ],
                test_plan=[
                    PlanStep(
                        command="pytest",
                        purpose="Run the regression suite.",
                        risk_covered="Static analysis and behavior regression.",
                    )
                ],
                risk_notes=["No write action is enabled."],
            )
        else:
            parsed = IssueToPrEvaluation(
                grounded=True,
                requires_more_context=False,
                risk_level="medium",
                findings=["Proposal cites collected evidence."],
                blocking_issues=[],
            )
        return SimpleNamespace(
            id=f"response-{len(self.calls)}",
            output_parsed=parsed,
            usage=SimpleNamespace(input_tokens=123, output_tokens=45),
        )


class FakeOpenAIClient:
    def __init__(self) -> None:
        self.responses = FakeResponses()


def create_planner_state(run_id: UUID) -> IssueToPrState:
    return {
        "run_id": run_id,
        "workflow_id": "engineering_issue_to_pr",
        "repository": "acme/app",
        "issue_number": 42,
        "ref": "main",
        "context_paths": ["src/service.py"],
        "autonomy_level": "draft_only",
        "actor_id": "user-123",
        "trace_id": "trace-1",
        "issue": {
            "title": "CI fails",
            "body": "Static analysis fails in CI.",
            "labels": ["bug"],
            "author": "maintainer",
            "url": "https://github.com/acme/app/issues/42",
        },
        "context_files": [
            {
                "path": "src/service.py",
                "ref": "main",
                "content": "def handler():\n    return 'ok'\n",
                "sha": "abc123",
            }
        ],
        "tool_call_ids": ["tool-call-1"],
        "policy_decision_ids": ["policy-1"],
        "evidence": [
            {
                "kind": "github_issue",
                "title": "CI fails",
                "source_uri": "https://github.com/acme/app/issues/42",
            }
        ],
    }


@pytest.mark.asyncio
async def test_openai_planner_records_model_calls_for_plan_and_evaluation() -> None:
    run_id = uuid4()
    session = PlannerSession()
    client = FakeOpenAIClient()
    planner = OpenAIIssueToPrPlanner(
        client=client,
        session=cast(Session, session),
        run_id=run_id,
        config=OpenAIPlannerConfig(model="gpt-5-mini"),
        trace_id="trace-1",
    )
    state = create_planner_state(run_id)

    proposal = await planner.create_patch_plan(state)
    evaluation = await planner.evaluate_patch_plan(state, proposal)

    assert proposal.write_actions_enabled is False
    assert evaluation.grounded is True
    assert len(client.responses.calls) == 2
    model_calls = [item for item in session.added if isinstance(item, ModelCall)]
    assert [call.purpose for call in model_calls] == [
        "issue_to_pr_patch_plan",
        "issue_to_pr_plan_evaluation",
    ]
    assert all(call.status == "succeeded" for call in model_calls)
    assert all(call.input_token_count == 123 for call in model_calls)
    assert all(call.output_token_count == 45 for call in model_calls)
    assert all(call.policy_context["write_actions_enabled"] is False for call in model_calls)
