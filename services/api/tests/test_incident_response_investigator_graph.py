from datetime import UTC, datetime
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
from aegisops_api.workflows.incident_response_investigator import (
    IncidentInvestigationGraphDependencies,
    IncidentInvestigationInput,
    IncidentTimeWindow,
    as_incident_investigation_state,
    create_incident_investigation_graph,
)


class FakeIncidentToolRuntime:
    def __init__(self) -> None:
        self.tool_by_call_id: dict[UUID, str] = {}
        self.run_by_call_id: dict[UUID, UUID] = {}
        self.authorized_inputs: list[dict[str, Any]] = []
        self.executed_inputs: list[dict[str, Any]] = []

    async def authorize_tool_call(
        self,
        request: ToolCallAuthorizationRequest,
    ) -> ToolCallAuthorizationResponse:
        tool_call_id = uuid4()
        self.tool_by_call_id[tool_call_id] = request.tool_id
        self.run_by_call_id[tool_call_id] = request.run_id
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
                decision_id=f"decision-{request.tool_id}",
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
        if tool_id == "observability_log_search":
            output_payload: dict[str, Any] = {
                "events": [
                    {
                        "event_id": "log-1",
                        "timestamp": "2026-07-15T07:00:00+00:00",
                        "severity": "error",
                        "service": "checkout-api",
                        "message": "database timeout",
                        "source_uri": "https://observability.example/events/log-1",
                    }
                ]
            }
        elif tool_id == "deployment_event_search":
            output_payload = {
                "deployments": [
                    {
                        "deployment_id": "dep-1",
                        "environment": "production",
                        "deployed_at": "2026-07-15T06:50:00+00:00",
                        "commit_sha": "abc123",
                        "status": "succeeded",
                        "source_uri": "https://deployments.example/events/dep-1",
                    }
                ]
            }
        else:
            output_payload = {
                "path": request.input_payload["path"],
                "ref": request.input_payload["ref"],
                "content": "timeout_ms = 250\n",
                "sha": "file-sha-1",
            }
        return ToolCallExecutionResponse(
            id=tool_call_id,
            run_id=self.run_by_call_id[tool_call_id],
            workflow_id="incident_response_investigator",
            tool_id=tool_id,
            status="succeeded",
            execution_state="executed",
            output_hash="hash",
            output_payload=output_payload,
            latency_ms=9,
        )


@pytest.mark.asyncio
async def test_incident_graph_collects_log_deployment_and_code_evidence() -> None:
    runtime = FakeIncidentToolRuntime()
    graph = create_incident_investigation_graph(
        IncidentInvestigationGraphDependencies(tool_runtime=runtime)
    )
    graph_input = IncidentInvestigationInput(
        run_id=uuid4(),
        incident_id="inc-001",
        service="checkout-api",
        time_window=IncidentTimeWindow(
            start=datetime(2026, 7, 15, 6, 45, tzinfo=UTC),
            end=datetime(2026, 7, 15, 7, 15, tzinfo=UTC),
        ),
        severity="error",
        environment="production",
        repository="acme/checkout",
        suspect_paths=["services/checkout/config.py"],
        actor_id="user-123",
    )

    result = as_incident_investigation_state(await graph.ainvoke(graph_input.to_initial_state()))

    assert result["log_events"][0]["event_id"] == "log-1"
    assert result["deployment_events"][0]["deployment_id"] == "dep-1"
    assert result["code_files"][0]["path"] == "services/checkout/config.py"
    assert [item["kind"] for item in result["evidence"]] == [
        "observability_log_event",
        "deployment_event",
        "github_file",
    ]
    assert [call["tool_id"] for call in runtime.authorized_inputs] == [
        "observability_log_search",
        "deployment_event_search",
        "github_file_read",
    ]
    assert [
        {"tool_id": call["tool_id"], "input_payload": call["input_payload"]}
        for call in runtime.authorized_inputs
    ] == runtime.executed_inputs


def test_incident_input_rejects_unsafe_suspect_paths() -> None:
    with pytest.raises(ValueError, match="relative repository file paths"):
        IncidentInvestigationInput(
            run_id=uuid4(),
            incident_id="inc-001",
            service="checkout-api",
            time_window=IncidentTimeWindow(
                start=datetime(2026, 7, 15, 6, 45, tzinfo=UTC),
                end=datetime(2026, 7, 15, 7, 15, tzinfo=UTC),
            ),
            repository="acme/checkout",
            suspect_paths=["../secrets.env"],
        )


def test_incident_time_window_requires_positive_duration() -> None:
    with pytest.raises(ValueError, match="time_window.end must be after"):
        IncidentTimeWindow(
            start=datetime(2026, 7, 15, 7, 15, tzinfo=UTC),
            end=datetime(2026, 7, 15, 6, 45, tzinfo=UTC),
        )
