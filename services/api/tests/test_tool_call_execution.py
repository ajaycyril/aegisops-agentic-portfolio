from pathlib import Path
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from aegisops_api.db.models import AuditEvent, ToolCall
from aegisops_api.main import app, get_database_session, get_tool_adapter_registry
from aegisops_api.tools.adapters import ToolAdapterExecutionError, ToolAdapterRegistry
from aegisops_api.tools.execution import (
    ToolCallExecutionRequest,
    execute_authorized_tool_call,
    hash_payload,
)
from aegisops_api.tools.registry import ToolRegistry

TOOL_CONFIG_DIR = Path(__file__).resolve().parents[3] / "configs" / "tools"


class FakeReadAdapter:
    def __init__(self, output_payload: dict[str, Any]) -> None:
        self.output_payload = output_payload
        self.inputs: list[dict[str, Any]] = []

    async def execute(self, _tool_id: str, input_payload: dict[str, Any]) -> dict[str, Any]:
        self.inputs.append(input_payload)
        return self.output_payload


class ToolExecutionSession:
    def __init__(self, tool_calls: dict[UUID, ToolCall]) -> None:
        self.tool_calls = tool_calls
        self.added: list[object] = []
        self.flush_count = 0
        self.commit_count = 0
        self.rollback_count = 0

    def add(self, instance: object) -> None:
        self.added.append(instance)

    def flush(self) -> None:
        self.flush_count += 1

    def commit(self) -> None:
        self.commit_count += 1

    def rollback(self) -> None:
        self.rollback_count += 1

    def get(self, model: object, identifier: object) -> object | None:
        if model is ToolCall:
            return self.tool_calls.get(cast(UUID, identifier))
        return None


def create_authorized_tool_call(input_payload: dict[str, Any]) -> ToolCall:
    return ToolCall(
        id=uuid4(),
        run_id=uuid4(),
        tool_name="github_issue_read",
        tool_version="schema-test",
        risk_class="read",
        input_schema_hash="input-schema-hash",
        input_hash=hash_payload(input_payload),
        status="pending",
        policy_decision_id="policy-decision-1",
        trace_id="trace-1",
        call_metadata={
            "workflow_id": "engineering_issue_to_pr",
            "tool_id": "github_issue_read",
            "connector": "github",
            "mcp_server": "aegisops.github",
            "execution_state": "authorized_not_executed",
        },
    )


def issue_output_payload() -> dict[str, Any]:
    return {
        "title": "Real issue",
        "body": "Issue body",
        "labels": ["bug"],
        "author": "octocat",
        "url": "https://github.com/owner/repo/issues/12",
    }


@pytest.mark.asyncio
async def test_execute_authorized_tool_call_records_success() -> None:
    input_payload = {"repository": "owner/repo", "issue_number": 12}
    tool_call = create_authorized_tool_call(input_payload)
    session = ToolExecutionSession({tool_call.id: tool_call})
    adapter = FakeReadAdapter(issue_output_payload())

    response = await execute_authorized_tool_call(
        tool_call_id=tool_call.id,
        request=ToolCallExecutionRequest(input_payload=input_payload, actor_id="user-123"),
        tool_registry=ToolRegistry.from_directory(TOOL_CONFIG_DIR),
        session=cast(Session, session),
        adapter_registry=ToolAdapterRegistry({"github_issue_read": adapter}),
    )

    assert response.status == "succeeded"
    assert response.execution_state == "executed"
    assert response.output_payload["title"] == "Real issue"
    assert tool_call.status == "succeeded"
    assert tool_call.output_hash == response.output_hash
    assert tool_call.call_metadata["execution_state"] == "executed"
    assert session.commit_count == 1
    assert session.rollback_count == 0
    assert any(isinstance(item, AuditEvent) for item in session.added)
    assert adapter.inputs == [input_payload]


@pytest.mark.asyncio
async def test_execute_endpoint_runs_only_matching_authorized_input() -> None:
    input_payload = {"repository": "owner/repo", "issue_number": 12}
    tool_call = create_authorized_tool_call(input_payload)
    session = ToolExecutionSession({tool_call.id: tool_call})
    adapter = FakeReadAdapter(issue_output_payload())

    def override_session() -> Any:
        yield cast(Session, session)

    def override_adapter_registry() -> ToolAdapterRegistry:
        return ToolAdapterRegistry({"github_issue_read": adapter})

    app.dependency_overrides[get_database_session] = override_session
    app.dependency_overrides[get_tool_adapter_registry] = override_adapter_registry
    try:
        client = TestClient(app)
        response = client.post(
            f"/tool-calls/{tool_call.id}/execute",
            json={"input_payload": input_payload, "actor_id": "user-123"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "succeeded"
    assert payload["output_payload"]["url"] == "https://github.com/owner/repo/issues/12"
    assert tool_call.status == "succeeded"


@pytest.mark.asyncio
async def test_execute_authorized_tool_call_records_failure_when_adapter_is_missing() -> None:
    input_payload = {"repository": "owner/repo", "issue_number": 12}
    tool_call = create_authorized_tool_call(input_payload)
    session = ToolExecutionSession({tool_call.id: tool_call})

    with pytest.raises(ToolAdapterExecutionError, match="No execution adapter"):
        await execute_authorized_tool_call(
            tool_call_id=tool_call.id,
            request=ToolCallExecutionRequest(input_payload=input_payload, actor_id="user-123"),
            tool_registry=ToolRegistry.from_directory(TOOL_CONFIG_DIR),
            session=cast(Session, session),
            adapter_registry=ToolAdapterRegistry({}),
        )

    assert tool_call.status == "failed"
    assert tool_call.call_metadata["execution_state"] == "failed"
    assert tool_call.call_metadata["adapter_reason_code"] == "tool_adapter_not_available"
    assert session.commit_count == 1
    assert any(isinstance(item, AuditEvent) for item in session.added)


@pytest.mark.asyncio
async def test_execute_endpoint_rejects_input_hash_mismatch() -> None:
    input_payload = {"repository": "owner/repo", "issue_number": 12}
    tool_call = create_authorized_tool_call(input_payload)
    session = ToolExecutionSession({tool_call.id: tool_call})
    adapter = FakeReadAdapter(issue_output_payload())

    def override_session() -> Any:
        yield cast(Session, session)

    def override_adapter_registry() -> ToolAdapterRegistry:
        return ToolAdapterRegistry({"github_issue_read": adapter})

    app.dependency_overrides[get_database_session] = override_session
    app.dependency_overrides[get_tool_adapter_registry] = override_adapter_registry
    try:
        client = TestClient(app)
        response = client.post(
            f"/tool-calls/{tool_call.id}/execute",
            json={
                "input_payload": {"repository": "owner/repo", "issue_number": 13},
                "actor_id": "user-123",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
    assert response.json()["detail"]["reason_code"] == "tool_input_hash_mismatch"
    assert tool_call.status == "pending"
    assert adapter.inputs == []
