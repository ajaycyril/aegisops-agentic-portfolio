from pathlib import Path
from typing import Any, cast

import yaml
from fastapi.testclient import TestClient

from aegisops_api.connectors.registry import ConnectorRegistry
from aegisops_api.main import app

REPO_ROOT = Path(__file__).resolve().parents[3]
CONNECTOR_CONFIG_DIR = REPO_ROOT / "configs" / "connectors"
TOOL_CONFIG_DIR = REPO_ROOT / "configs" / "tools"
WORKFLOW_CONFIG_DIR = REPO_ROOT / "configs" / "workflows"


def load_yaml_mapping(path: Path) -> dict[str, Any]:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return cast(dict[str, Any], loaded)


def test_connector_registry_loads_catalog_disabled_by_default() -> None:
    registry = ConnectorRegistry.from_directory(CONNECTOR_CONFIG_DIR)

    connectors = registry.list_connectors(environment={})

    assert len(connectors) >= 17
    assert all(connector.deployment_enabled is False for connector in connectors)
    assert all(connector.ready is False for connector in connectors)
    github = next(connector for connector in connectors if connector.id == "github")
    assert github.status == "contract_ready"
    assert github.auth_type == "github_app"


def test_connector_registry_reports_missing_env_names_without_values() -> None:
    registry = ConnectorRegistry.from_directory(CONNECTOR_CONFIG_DIR)

    github = registry.get_connector(
        "github",
        configured_connectors={"github"},
        environment={},
    )

    assert github.deployment_enabled is True
    assert github.auth_configured is False
    assert github.ready is False
    assert github.missing_env_vars == [
        "GITHUB_APP_ID",
        "GITHUB_APP_PRIVATE_KEY",
        "GITHUB_WEBHOOK_SECRET",
    ]


def test_connector_registry_marks_contract_ready_when_enabled_and_authenticated() -> None:
    registry = ConnectorRegistry.from_directory(CONNECTOR_CONFIG_DIR)

    github = registry.get_connector(
        "github",
        configured_connectors={"github"},
        environment={
            "GITHUB_APP_ID": "present",
            "GITHUB_APP_PRIVATE_KEY": "present",
            "GITHUB_WEBHOOK_SECRET": "present",
        },
    )

    assert github.auth_configured is True
    assert github.ready is True
    assert github.disabled_reason is None


def test_connector_catalog_covers_workflow_and_tool_configs() -> None:
    registry = ConnectorRegistry.from_directory(CONNECTOR_CONFIG_DIR)
    connector_ids = {connector.id for connector in registry.list_connectors(environment={})}

    workflow_connectors: set[str] = set()
    workflow_ids: set[str] = set()
    for path in WORKFLOW_CONFIG_DIR.glob("*.yaml"):
        workflow = load_yaml_mapping(path)
        workflow_ids.add(str(workflow["id"]))
        enabled_when = cast(dict[str, Any], workflow["enabled_when"])
        workflow_connectors.update(str(connector) for connector in enabled_when["connectors"])

    tool_connectors: set[str] = set()
    tool_ids: set[str] = set()
    for path in TOOL_CONFIG_DIR.glob("*.yaml"):
        tool = load_yaml_mapping(path)
        tool_ids.add(str(tool["id"]))
        tool_connectors.add(str(tool["connector"]))

    assert workflow_connectors <= connector_ids
    assert tool_connectors <= connector_ids

    for connector_id in sorted(workflow_connectors | tool_connectors):
        connector = registry.get_connector(connector_id, environment={})
        assert set(connector.workflow_ids) <= workflow_ids
        assert set(connector.tool_ids) <= tool_ids


def test_connectors_endpoint_lists_readiness_contracts() -> None:
    client = TestClient(app)

    response = client.get("/connectors")

    assert response.status_code == 200
    payload = response.json()
    assert {connector["id"] for connector in payload} >= {
        "github",
        "postgres",
        "document_store",
        "observability",
    }
    assert all(connector["ready"] is False for connector in payload)


def test_connector_detail_endpoint_returns_auth_and_data_boundaries() -> None:
    client = TestClient(app)

    response = client.get("/connectors/github")

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == "github"
    assert payload["auth_type"] == "github_app"
    assert payload["required_env_vars"] == [
        "GITHUB_APP_ID",
        "GITHUB_APP_PRIVATE_KEY",
        "GITHUB_WEBHOOK_SECRET",
    ]
    assert payload["data_boundaries"]["permitted_data_classes"] == [
        "source_code",
        "issue_metadata",
        "pull_request_metadata",
    ]


def test_connector_detail_endpoint_returns_404_for_unknown_connector() -> None:
    client = TestClient(app)

    response = client.get("/connectors/not_a_connector")

    assert response.status_code == 404
