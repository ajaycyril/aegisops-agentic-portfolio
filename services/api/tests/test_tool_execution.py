from pathlib import Path
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from aegisops_api.db.models import Approval, AuditEvent, ToolCall
from aegisops_api.main import app, get_database_session, get_tool_policy_evaluator
from aegisops_api.policy import PolicyDecision
from aegisops_api.tools import ToolPolicyEvaluator
from aegisops_api.tools.execution import (
    ToolCallAuthorizationRequest,
    ToolExecutionRejectedError,
    authorize_tool_call,
)
from aegisops_api.tools.mcp_server import create_tool_contract_mcp_server
from aegisops_api.tools.registry import ToolRegistry
from aegisops_api.workflows.registry import WorkflowRegistry

TOOL_CONFIG_DIR = Path(__file__).resolve().parents[3] / "configs" / "tools"


class RecordingSession:
    def __init__(self, approvals: dict[UUID, Approval] | None = None) -> None:
        self.approvals = approvals or {}
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

    def get(self, _model: object, identifier: object) -> object | None:
        return self.approvals.get(cast(UUID, identifier))


class FakeToolPolicyEvaluator:
    def __init__(self, decision: PolicyDecision) -> None:
        self.decision = decision
        self.inputs: list[dict[str, Any]] = []

    async def evaluate(self, input_payload: dict[str, Any]) -> PolicyDecision:
        self.inputs.append(input_payload)
        return self.decision


def create_ready_registry(tmp_path: Path) -> WorkflowRegistry:
    config_path = tmp_path / "ready_engineering.yaml"
    config_path.write_text(
        "\n".join(
            [
                "id: engineering_issue_to_pr",
                "name: Ready Engineering Agent",
                "domain: engineering",
                "status: ready",
                "enabled_when:",
                "  connectors: [github]",
                "  required_scopes: [issues:read]",
                "patterns: [plan_execute]",
                "data_policy:",
                "  fake_data_allowed: false",
                "  replay_allowed_from_real_runs: true",
                "  regex_business_extraction_allowed: false",
                "default_autonomy: draft_only",
                "approval_required_for: [pull_request_creation]",
                "visual_surfaces: [executive_summary]",
            ]
        ),
        encoding="utf-8",
    )
    return WorkflowRegistry.from_directory(tmp_path)


@pytest.mark.asyncio
async def test_authorize_tool_call_records_pending_read_tool(tmp_path: Path) -> None:
    run_id = uuid4()
    session = RecordingSession()
    evaluator = FakeToolPolicyEvaluator(
        PolicyDecision(
            package_path="aegisops.tool_access",
            allowed=True,
            requires_approval=False,
            decision_id="tool-decision-1",
            reason_codes=[],
            result={"allow": True, "requires_approval": False, "reason_codes": []},
        )
    )

    response = await authorize_tool_call(
        request=ToolCallAuthorizationRequest(
            run_id=run_id,
            workflow_id="engineering_issue_to_pr",
            tool_id="github_issue_read",
            autonomy_level="draft_only",
            input_payload={"repository": "owner/repo", "issue_number": 12},
            actor_id="user-123",
        ),
        workflow_registry=create_ready_registry(tmp_path),
        tool_registry=ToolRegistry.from_directory(TOOL_CONFIG_DIR),
        session=cast(Session, session),
        policy_evaluator=evaluator,
        available_connectors={"github"},
    )

    assert response.status == "pending"
    assert response.execution_state == "authorized_not_executed"
    assert session.commit_count == 1
    assert session.rollback_count == 0
    assert any(isinstance(item, ToolCall) for item in session.added)
    assert any(isinstance(item, AuditEvent) for item in session.added)
    assert evaluator.inputs[0]["tool"]["risk_class"] == "read"
    assert evaluator.inputs[0]["connector_ready"] is True


@pytest.mark.asyncio
async def test_authorize_tool_call_records_blocked_write_tool_when_approval_required(
    tmp_path: Path,
) -> None:
    session = RecordingSession()
    evaluator = FakeToolPolicyEvaluator(
        PolicyDecision(
            package_path="aegisops.tool_access",
            allowed=False,
            requires_approval=True,
            decision_id="tool-decision-approval",
            reason_codes=["approval_required"],
            result={
                "allow": False,
                "requires_approval": True,
                "reason_codes": ["approval_required"],
            },
        )
    )

    response = await authorize_tool_call(
        request=ToolCallAuthorizationRequest(
            run_id=uuid4(),
            workflow_id="engineering_issue_to_pr",
            tool_id="github_pull_request_draft",
            autonomy_level="approval_required",
            input_payload={
                "repository": "owner/repo",
                "title": "Fix issue",
                "body": "Draft PR body",
                "head_branch": "aegis/fix-issue",
                "base_branch": "main",
            },
        ),
        workflow_registry=create_ready_registry(tmp_path),
        tool_registry=ToolRegistry.from_directory(TOOL_CONFIG_DIR),
        session=cast(Session, session),
        policy_evaluator=evaluator,
        available_connectors={"github"},
    )

    assert response.status == "blocked"
    assert response.execution_state == "blocked_before_execution"
    assert response.policy_decision.requires_approval is True
    assert session.commit_count == 1
    tool_call = next(item for item in session.added if isinstance(item, ToolCall))
    assert tool_call.status == "blocked"


@pytest.mark.asyncio
async def test_authorize_tool_call_rejects_invalid_input_before_policy(tmp_path: Path) -> None:
    evaluator = FakeToolPolicyEvaluator(
        PolicyDecision(package_path="aegisops.tool_access", allowed=True, result={"allow": True})
    )

    with pytest.raises(ToolExecutionRejectedError, match="schema validation"):
        await authorize_tool_call(
            request=ToolCallAuthorizationRequest(
                run_id=uuid4(),
                workflow_id="engineering_issue_to_pr",
                tool_id="github_issue_read",
                autonomy_level="draft_only",
                input_payload={"repository": "owner/repo"},
            ),
            workflow_registry=create_ready_registry(tmp_path),
            tool_registry=ToolRegistry.from_directory(TOOL_CONFIG_DIR),
            session=cast(Session, RecordingSession()),
            policy_evaluator=evaluator,
            available_connectors={"github"},
        )

    assert evaluator.inputs == []


@pytest.mark.asyncio
async def test_authorize_tool_call_uses_verified_approved_approval(tmp_path: Path) -> None:
    run_id = uuid4()
    approval_id = uuid4()
    session = RecordingSession(
        approvals={
            approval_id: Approval(
                id=approval_id,
                run_id=run_id,
                status="approved",
                risk_class="write",
                requested_action="pull_request_creation",
                requested_by="user-123",
            )
        }
    )
    evaluator = FakeToolPolicyEvaluator(
        PolicyDecision(
            package_path="aegisops.tool_access",
            allowed=True,
            requires_approval=False,
            decision_id="tool-decision-approved",
            reason_codes=[],
            result={"allow": True, "requires_approval": False, "reason_codes": []},
        )
    )

    await authorize_tool_call(
        request=ToolCallAuthorizationRequest(
            run_id=run_id,
            workflow_id="engineering_issue_to_pr",
            tool_id="github_pull_request_draft",
            autonomy_level="approval_required",
            approval_id=approval_id,
            input_payload={
                "repository": "owner/repo",
                "title": "Fix issue",
                "body": "Draft PR body",
                "head_branch": "aegis/fix-issue",
                "base_branch": "main",
            },
        ),
        workflow_registry=create_ready_registry(tmp_path),
        tool_registry=ToolRegistry.from_directory(TOOL_CONFIG_DIR),
        session=cast(Session, session),
        policy_evaluator=evaluator,
        available_connectors={"github"},
    )

    assert evaluator.inputs[0]["approval"]["status"] == "approved"
    tool_call = next(item for item in session.added if isinstance(item, ToolCall))
    assert tool_call.approval_id == approval_id


def test_tool_authorization_endpoint_reports_planned_workflow_rejection() -> None:
    def override_session() -> Any:
        yield cast(Session, RecordingSession())

    async def override_policy() -> ToolPolicyEvaluator:
        return FakeToolPolicyEvaluator(
            PolicyDecision(
                package_path="aegisops.tool_access",
                allowed=True,
                result={"allow": True},
            )
        )

    app.dependency_overrides[get_database_session] = override_session
    app.dependency_overrides[get_tool_policy_evaluator] = override_policy
    try:
        client = TestClient(app)
        response = client.post(
            "/tool-calls/authorize",
            json={
                "run_id": str(uuid4()),
                "workflow_id": "engineering_issue_to_pr",
                "tool_id": "github_issue_read",
                "autonomy_level": "draft_only",
                "input_payload": {"repository": "owner/repo", "issue_number": 12},
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
    assert response.json()["detail"]["reason_code"] == "workflow_not_ready"


@pytest.mark.asyncio
async def test_mcp_server_exposes_contract_tools() -> None:
    server = create_tool_contract_mcp_server(
        tool_registry=ToolRegistry.from_directory(TOOL_CONFIG_DIR),
        available_connectors={"github"},
    )

    tools = await server.list_tools()

    assert {tool.name for tool in tools} >= {"list_tool_contracts", "get_tool_contract"}
