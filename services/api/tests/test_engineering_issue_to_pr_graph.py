from typing import Any
from uuid import UUID, uuid4

import pytest

from aegisops_api.tools import (
    ToolCallAuthorizationRequest,
    ToolCallAuthorizationResponse,
    ToolCallExecutionRequest,
    ToolCallExecutionResponse,
)
from aegisops_api.tools.execution import ToolPolicyDecisionSummary
from aegisops_api.workflows.engineering_issue_to_pr import (
    IssueToPrGraphDependencies,
    IssueToPrGraphInput,
    create_engineering_issue_to_pr_graph,
)
from aegisops_api.workflows.engineering_issue_to_pr.graph import (
    IssueToPrEvaluation,
    IssueToPrProposal,
    IssueToPrState,
    PlannedFileChange,
    as_issue_to_pr_state,
)
from aegisops_api.workflows.engineering_issue_to_pr.graph import (
    TestPlanStep as PlanStep,
)


class FakeIssueToPrToolRuntime:
    def __init__(self) -> None:
        self.tool_by_call_id: dict[UUID, str] = {}
        self.authorized_inputs: list[dict[str, Any]] = []
        self.executed_inputs: list[dict[str, Any]] = []

    async def authorize_tool_call(
        self,
        request: ToolCallAuthorizationRequest,
    ) -> ToolCallAuthorizationResponse:
        tool_call_id = uuid4()
        self.tool_by_call_id[tool_call_id] = request.tool_id
        self.authorized_inputs.append(
            {
                "tool_id": request.tool_id,
                "input_payload": request.input_payload,
                "autonomy_level": request.autonomy_level,
            }
        )
        return ToolCallAuthorizationResponse(
            id=tool_call_id,
            run_id=request.run_id,
            workflow_id=request.workflow_id,
            tool_id=request.tool_id,
            status="pending",
            execution_state="authorized_not_executed",
            risk_class="read",
            policy_decision=ToolPolicyDecisionSummary(
                allowed=True,
                requires_approval=False,
                decision_id="decision-1",
                reason_codes=[],
            ),
        )

    async def execute_tool_call(
        self,
        tool_call_id: UUID,
        request: ToolCallExecutionRequest,
    ) -> ToolCallExecutionResponse:
        tool_id = self.tool_by_call_id[tool_call_id]
        self.executed_inputs.append({"tool_id": tool_id, "input_payload": request.input_payload})
        if tool_id == "github_issue_read":
            output_payload = {
                "title": "Fix failing workflow",
                "body": "The CI workflow fails on type checking.",
                "labels": ["bug"],
                "author": "octocat",
                "url": "https://github.com/owner/repo/issues/12",
            }
        else:
            output_payload = {
                "path": request.input_payload["path"],
                "ref": request.input_payload["ref"],
                "content": "print('hello')\n",
                "sha": "abc123",
            }
        return ToolCallExecutionResponse(
            id=tool_call_id,
            run_id=uuid4(),
            workflow_id="engineering_issue_to_pr",
            tool_id=tool_id,
            status="succeeded",
            execution_state="executed",
            output_hash="hash",
            output_payload=output_payload,
            latency_ms=12,
        )


class FakeIssueToPrPlanner:
    async def create_patch_plan(self, state: IssueToPrState) -> IssueToPrProposal:
        return IssueToPrProposal(
            summary="Plan a minimal guarded patch.",
            problem_statement=str(state["issue"]["title"]),
            source_evidence_uris=[item["source_uri"] for item in state["evidence"]],
            planned_changes=[
                PlannedFileChange(
                    path="src/app.py",
                    change_type="modify",
                    rationale="Align implementation with the captured issue evidence.",
                    evidence_uris=["https://github.com/owner/repo/issues/12"],
                )
            ],
            test_plan=[
                PlanStep(
                    command="pytest",
                    purpose="Run the relevant Python regression suite.",
                    risk_covered="Avoid introducing a behavior regression.",
                )
            ],
            risk_notes=["Write actions remain disabled until human approval is wired."],
        )

    async def evaluate_patch_plan(
        self,
        _state: IssueToPrState,
        proposal: IssueToPrProposal,
    ) -> IssueToPrEvaluation:
        return IssueToPrEvaluation(
            grounded=bool(proposal.source_evidence_uris),
            requires_more_context=False,
            risk_level="medium",
            findings=["Proposal references collected GitHub evidence."],
            blocking_issues=[],
        )


@pytest.mark.asyncio
async def test_engineering_issue_to_pr_graph_reads_issue_and_context_files() -> None:
    runtime = FakeIssueToPrToolRuntime()
    graph = create_engineering_issue_to_pr_graph(IssueToPrGraphDependencies(tool_runtime=runtime))
    graph_input = IssueToPrGraphInput(
        run_id=uuid4(),
        repository="owner/repo",
        issue_number=12,
        ref="main",
        context_paths=["src/app.py"],
        actor_id="user-123",
    )

    result = as_issue_to_pr_state(await graph.ainvoke(graph_input.to_initial_state()))

    assert result["issue"]["title"] == "Fix failing workflow"
    assert result["context_files"] == [
        {
            "path": "src/app.py",
            "ref": "main",
            "content": "print('hello')\n",
            "sha": "abc123",
        }
    ]
    assert result["evidence"] == [
        {
            "kind": "github_issue",
            "title": "Fix failing workflow",
            "source_uri": "https://github.com/owner/repo/issues/12",
            "tool_call_id": result["tool_call_ids"][0],
        },
        {
            "kind": "github_file",
            "title": "src/app.py",
            "source_uri": "https://github.com/owner/repo/blob/main/src/app.py",
            "sha": "abc123",
        },
    ]
    assert [call["tool_id"] for call in runtime.authorized_inputs] == [
        "github_issue_read",
        "github_file_read",
    ]
    assert [
        {"tool_id": call["tool_id"], "input_payload": call["input_payload"]}
        for call in runtime.authorized_inputs
    ] == runtime.executed_inputs


@pytest.mark.asyncio
async def test_engineering_graph_adds_plan_and_evaluation_when_planner_present() -> None:
    runtime = FakeIssueToPrToolRuntime()
    graph = create_engineering_issue_to_pr_graph(
        IssueToPrGraphDependencies(
            tool_runtime=runtime,
            planner=FakeIssueToPrPlanner(),
        )
    )
    graph_input = IssueToPrGraphInput(
        run_id=uuid4(),
        repository="owner/repo",
        issue_number=12,
        ref="main",
        context_paths=["src/app.py"],
    )

    result = as_issue_to_pr_state(await graph.ainvoke(graph_input.to_initial_state()))

    assert result["proposal"]["approval_required"] is True
    assert result["proposal"]["write_actions_enabled"] is False
    assert result["proposal"]["planned_changes"][0]["path"] == "src/app.py"
    assert result["evaluation"]["grounded"] is True
    assert result["evaluation"]["risk_level"] == "medium"


def test_engineering_issue_to_pr_input_rejects_unsafe_context_paths() -> None:
    with pytest.raises(ValueError, match="relative repository file paths"):
        IssueToPrGraphInput(
            run_id=uuid4(),
            repository="owner/repo",
            issue_number=12,
            context_paths=["../secrets.env"],
        )
