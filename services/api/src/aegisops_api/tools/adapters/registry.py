from __future__ import annotations

from typing import Any

from aegisops_api.connectors.registry import get_connector_environment
from aegisops_api.tools.adapters.base import (
    ToolAdapter,
    ToolAdapterExecutionError,
    ToolAdapterNotFoundError,
)
from aegisops_api.tools.adapters.github import GitHubAppToolAdapter

GITHUB_REQUIRED_ENV_VARS = ("GITHUB_APP_ID", "GITHUB_APP_PRIVATE_KEY")


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
    github_adapter: ToolAdapter
    if missing_github_env_vars:
        github_adapter = MissingConnectorAuthToolAdapter("GitHub", missing_github_env_vars)
    else:
        github_adapter = GitHubAppToolAdapter.from_environment(environment)
    return ToolAdapterRegistry(
        adapters={
            "github_file_read": github_adapter,
            "github_issue_read": github_adapter,
        }
    )
