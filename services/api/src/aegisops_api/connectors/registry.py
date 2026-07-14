from __future__ import annotations

import os
from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal, cast

import yaml
from dotenv import dotenv_values
from pydantic import BaseModel, ConfigDict, Field

from aegisops_api.config import Settings, get_settings
from aegisops_api.workflows.registry import get_available_connectors

ConnectorStatus = Literal["contract_ready", "planned", "disabled"]
ConnectorAuthType = Literal[
    "api_key",
    "connection_profile",
    "database_url",
    "github_app",
    "none",
    "oauth",
    "otlp",
    "public_dataset",
]

DEFAULT_CONNECTOR_CONFIG_DIR = Path(__file__).resolve().parents[5] / "configs" / "connectors"


class ConnectorRegistryError(RuntimeError):
    pass


class ConnectorNotFoundError(LookupError):
    pass


class DataBoundaries(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stores_personal_data: bool
    stores_customer_data: bool
    external_network_access: bool
    permitted_data_classes: list[str] = Field(default_factory=list)


class ConnectorConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    provider: str
    category: str
    status: ConnectorStatus
    auth_type: ConnectorAuthType
    required_env_vars: list[str] = Field(default_factory=list)
    supported_scopes: list[str] = Field(default_factory=list)
    tool_ids: list[str] = Field(default_factory=list)
    workflow_ids: list[str] = Field(default_factory=list)
    data_boundaries: DataBoundaries


class ConnectorSummary(BaseModel):
    id: str
    name: str
    provider: str
    category: str
    status: ConnectorStatus
    auth_type: ConnectorAuthType
    deployment_enabled: bool
    auth_configured: bool
    ready: bool
    disabled_reason: str | None
    required_env_vars: list[str]
    missing_env_vars: list[str]
    supported_scopes: list[str]


class ConnectorDetail(ConnectorSummary):
    tool_ids: list[str]
    workflow_ids: list[str]
    data_boundaries: DataBoundaries
    source_path: str


class ConnectorRegistry:
    def __init__(
        self,
        connectors: dict[str, ConnectorConfig],
        source_paths: dict[str, Path],
    ) -> None:
        self._connectors = connectors
        self._source_paths = source_paths

    @classmethod
    def from_directory(cls, config_dir: Path) -> ConnectorRegistry:
        if not config_dir.exists():
            raise ConnectorRegistryError(f"connector config directory does not exist: {config_dir}")

        connectors: dict[str, ConnectorConfig] = {}
        source_paths: dict[str, Path] = {}
        for config_path in sorted(config_dir.glob("*.yaml")):
            connector = load_connector_config(config_path)
            if connector.id in connectors:
                raise ConnectorRegistryError(f"duplicate connector id: {connector.id}")
            connectors[connector.id] = connector
            source_paths[connector.id] = config_path

        if not connectors:
            raise ConnectorRegistryError(f"no connector configs found in {config_dir}")

        return cls(connectors=connectors, source_paths=source_paths)

    def list_connectors(
        self,
        configured_connectors: set[str] | None = None,
        environment: Mapping[str, str] | None = None,
    ) -> list[ConnectorSummary]:
        configured = configured_connectors or set()
        env = environment or get_connector_environment()
        return [
            connector_to_summary(connector, configured, env)
            for connector in sorted(self._connectors.values(), key=lambda item: item.id)
        ]

    def get_connector(
        self,
        connector_id: str,
        configured_connectors: set[str] | None = None,
        environment: Mapping[str, str] | None = None,
    ) -> ConnectorDetail:
        connector = self._connectors.get(connector_id)
        if connector is None:
            raise ConnectorNotFoundError(connector_id)

        summary = connector_to_summary(
            connector,
            configured_connectors or set(),
            environment or get_connector_environment(),
        )
        return ConnectorDetail(
            **summary.model_dump(),
            tool_ids=connector.tool_ids,
            workflow_ids=connector.workflow_ids,
            data_boundaries=connector.data_boundaries,
            source_path=str(self._source_paths[connector.id]),
        )


def load_connector_config(config_path: Path) -> ConnectorConfig:
    loaded = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ConnectorRegistryError(f"connector config must be a mapping: {config_path}")
    payload = cast(dict[str, Any], loaded)
    return ConnectorConfig.model_validate(payload)


def connector_to_summary(
    connector: ConnectorConfig,
    configured_connectors: set[str],
    environment: Mapping[str, str],
) -> ConnectorSummary:
    deployment_enabled = connector.id in configured_connectors
    missing_env_vars = [
        env_var for env_var in connector.required_env_vars if not environment.get(env_var)
    ]
    auth_configured = not missing_env_vars
    ready = connector.status == "contract_ready" and deployment_enabled and auth_configured
    disabled_reason = None
    if connector.status != "contract_ready":
        disabled_reason = f"connector status is {connector.status}"
    elif not deployment_enabled:
        disabled_reason = "connector is not listed in CONFIGURED_CONNECTORS"
    elif not auth_configured:
        disabled_reason = "connector auth environment is incomplete"

    return ConnectorSummary(
        id=connector.id,
        name=connector.name,
        provider=connector.provider,
        category=connector.category,
        status=connector.status,
        auth_type=connector.auth_type,
        deployment_enabled=deployment_enabled,
        auth_configured=auth_configured,
        ready=ready,
        disabled_reason=disabled_reason,
        required_env_vars=connector.required_env_vars,
        missing_env_vars=missing_env_vars,
        supported_scopes=connector.supported_scopes,
    )


def get_connector_environment(env_file: Path | None = None) -> Mapping[str, str]:
    values: dict[str, str] = {}
    resolved_env_file = env_file or Path.cwd() / ".env"
    if resolved_env_file.exists():
        for key, value in dotenv_values(resolved_env_file).items():
            if value:
                values[key] = value
    values.update({key: value for key, value in os.environ.items() if value})
    return values


def get_connector_config_dir(settings: Settings | None = None) -> Path:
    resolved_settings = settings or get_settings()
    return resolved_settings.connector_config_dir or DEFAULT_CONNECTOR_CONFIG_DIR


@lru_cache
def get_connector_registry(config_dir: str | None = None) -> ConnectorRegistry:
    resolved_config_dir = Path(config_dir) if config_dir is not None else get_connector_config_dir()
    return ConnectorRegistry.from_directory(resolved_config_dir)


def list_connector_readiness(settings: Settings | None = None) -> list[ConnectorSummary]:
    resolved_settings = settings or get_settings()
    return get_connector_registry(str(get_connector_config_dir(resolved_settings))).list_connectors(
        configured_connectors=get_available_connectors(resolved_settings),
    )
