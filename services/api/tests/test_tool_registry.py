from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from aegisops_api.main import app
from aegisops_api.tools.registry import ToolRegistry

TOOL_CONFIG_DIR = Path(__file__).resolve().parents[3] / "configs" / "tools"


def test_tool_registry_loads_contracts_disabled_by_default() -> None:
    registry = ToolRegistry.from_directory(TOOL_CONFIG_DIR)

    tools = registry.list_tools()

    assert len(tools) >= 6
    assert all(tool.enabled is False for tool in tools)
    pull_request_tool = next(tool for tool in tools if tool.id == "github_pull_request_draft")
    assert pull_request_tool.risk_class == "write"
    assert pull_request_tool.requires_approval is True


def test_tool_registry_reports_connector_ready_when_configured() -> None:
    registry = ToolRegistry.from_directory(TOOL_CONFIG_DIR)

    tools = registry.list_tools(available_connectors={"github"})

    issue_tool = next(tool for tool in tools if tool.id == "github_issue_read")
    pull_request_tool = next(tool for tool in tools if tool.id == "github_pull_request_draft")
    assert issue_tool.enabled is True
    assert pull_request_tool.enabled is True
    assert pull_request_tool.requires_approval is True


def test_tool_detail_exposes_typed_json_schemas() -> None:
    registry = ToolRegistry.from_directory(TOOL_CONFIG_DIR)

    tool = registry.get_tool("github_issue_read")

    assert tool.input_schema["type"] == "object"
    assert tool.output_schema["type"] == "object"
    assert tool.input_schema["properties"]["repository"]["type"] == "string"


def test_write_class_tool_requires_approval_by_default(tmp_path: Path) -> None:
    (tmp_path / "unsafe_write.yaml").write_text(
        "\n".join(
            [
                "id: unsafe_write",
                "name: Unsafe Write",
                "description: Invalid write tool.",
                "connector: github",
                "mcp_server: aegisops.github",
                "status: contract_ready",
                "risk_class: write",
                "required_scopes: [pull_requests:write]",
                "allowed_workflows: [engineering_issue_to_pr]",
                "approval_required: false",
                "input_schema:",
                "  type: object",
                "output_schema:",
                "  type: object",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="write-class tools must require approval"):
        ToolRegistry.from_directory(tmp_path)


def test_tools_endpoint_lists_disabled_tool_contracts() -> None:
    client = TestClient(app)

    response = client.get("/tools")

    assert response.status_code == 200
    payload = response.json()
    assert {tool["id"] for tool in payload} >= {
        "github_issue_read",
        "github_pull_request_draft",
        "observability_log_search",
    }
    assert all(tool["enabled"] is False for tool in payload)


def test_tool_detail_endpoint_returns_schema_contract() -> None:
    client = TestClient(app)

    response = client.get("/tools/github_issue_read")

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == "github_issue_read"
    assert payload["risk_class"] == "read"
    assert payload["input_schema"]["type"] == "object"


def test_tool_detail_endpoint_returns_404_for_unknown_tool() -> None:
    client = TestClient(app)

    response = client.get("/tools/not_a_tool")

    assert response.status_code == 404
