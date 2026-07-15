from __future__ import annotations

from typing import Any

from aegisops_api.connectors.registry import get_connector_environment
from aegisops_api.tools.adapters.base import (
    ToolAdapter,
    ToolAdapterExecutionError,
    ToolAdapterNotFoundError,
)
from aegisops_api.tools.adapters.github import GitHubAppToolAdapter
from aegisops_api.tools.adapters.http_json import (
    DeploymentEventSearchAdapter,
    ObservabilityLogSearchAdapter,
)

GITHUB_REQUIRED_ENV_VARS = ("GITHUB_APP_ID", "GITHUB_APP_PRIVATE_KEY")
OBSERVABILITY_REQUIRED_ENV_VARS = (
    "OBSERVABILITY_CONNECTION_ID",
    "OBSERVABILITY_API_BASE_URL",
)
DEPLOYMENTS_REQUIRED_ENV_VARS = (
    "DEPLOYMENTS_CONNECTION_ID",
    "DEPLOYMENTS_API_BASE_URL",
)


class MissingConnectorAuthToolAdapter:
    def __init__(self, connector: str, missing_env_vars: list[str]) -> None:
        self._connector = connector
        self._missing_env_vars = missing_env_vars

    async def execute(self, _tool_id: str, _input_payload: dict[str, Any]) -> dict[str, Any]:
        raise ToolAdapterExecutionError(
            reason_code="connector_auth_missing",
            message=(
                f"{self._connector} adapter is missing required env vars: "
                f"{', '.join(self._missing_env_vars)}."
            ),
            http_status=503,
        )


class ContractOnlyToolAdapter:
    def __init__(self, connector: str) -> None:
        self._connector = connector

    async def execute(self, tool_id: str, _input_payload: dict[str, Any]) -> dict[str, Any]:
        raise ToolAdapterExecutionError(
            reason_code="connector_adapter_not_configured",
            message=(
                f"{self._connector} tool {tool_id} has a production contract, but no live "
                "adapter implementation is configured in this build."
            ),
            http_status=501,
        )


class ToolAdapterRegistry:
    def __init__(self, adapters: dict[str, ToolAdapter]) -> None:
        self._adapters = adapters

    def get_adapter(self, tool_id: str) -> ToolAdapter:
        adapter = self._adapters.get(tool_id)
        if adapter is None:
            raise ToolAdapterNotFoundError(tool_id)
        return adapter


def create_default_tool_adapter_registry() -> ToolAdapterRegistry:
    environment = get_connector_environment()
    missing_github_env_vars = [
        env_var for env_var in GITHUB_REQUIRED_ENV_VARS if not environment.get(env_var)
    ]
    missing_observability_env_vars = [
        env_var for env_var in OBSERVABILITY_REQUIRED_ENV_VARS if not environment.get(env_var)
    ]
    missing_deployments_env_vars = [
        env_var for env_var in DEPLOYMENTS_REQUIRED_ENV_VARS if not environment.get(env_var)
    ]
    github_adapter: ToolAdapter
    if missing_github_env_vars:
        github_adapter = MissingConnectorAuthToolAdapter("GitHub", missing_github_env_vars)
    else:
        github_adapter = GitHubAppToolAdapter.from_environment(environment)
    observability_adapter: ToolAdapter
    if missing_observability_env_vars:
        observability_adapter = MissingConnectorAuthToolAdapter(
            "Observability",
            missing_observability_env_vars,
        )
    else:
        observability_adapter = ObservabilityLogSearchAdapter.from_environment(environment)
    deployments_adapter: ToolAdapter
    if missing_deployments_env_vars:
        deployments_adapter = MissingConnectorAuthToolAdapter(
            "Deployment Events",
            missing_deployments_env_vars,
        )
    else:
        deployments_adapter = DeploymentEventSearchAdapter.from_environment(environment)
    return ToolAdapterRegistry(
        adapters={
            "github_file_read": github_adapter,
            "github_issue_read": github_adapter,
            "observability_log_search": observability_adapter,
            "deployment_event_search": deployments_adapter,
        }
    )
