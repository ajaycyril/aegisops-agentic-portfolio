from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Literal, Self, cast

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

ToolRiskClass = Literal["read", "draft", "write", "external_message", "financial", "access_change"]
ToolStatus = Literal["contract_ready", "planned", "disabled"]

DEFAULT_TOOL_CONFIG_DIR = Path(__file__).resolve().parents[5] / "configs" / "tools"
WRITE_RISK_CLASSES: set[ToolRiskClass] = {
    "write",
    "external_message",
    "financial",
    "access_change",
}


class ToolRegistryError(RuntimeError):
    pass


class ToolNotFoundError(LookupError):
    pass


class JsonSchemaObject(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: str = "object"

    @model_validator(mode="after")
    def validate_schema_root(self) -> Self:
        if self.type != "object":
            raise ValueError("tool schemas must have an object root")
        return self


class ToolConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    description: str
    connector: str
    mcp_server: str
    status: ToolStatus
    risk_class: ToolRiskClass
    required_scopes: list[str] = Field(min_length=1)
    allowed_workflows: list[str] = Field(min_length=1)
    input_schema: JsonSchemaObject
    output_schema: JsonSchemaObject
    approval_required: bool | None = None

    @model_validator(mode="after")
    def validate_write_tools_require_approval(self) -> Self:
        if self.risk_class in WRITE_RISK_CLASSES and self.approval_required is not True:
            raise ValueError("write-class tools must require approval by default")
        return self

    @property
    def requires_approval(self) -> bool:
        return self.approval_required is True or self.risk_class in WRITE_RISK_CLASSES


class ToolSummary(BaseModel):
    id: str
    name: str
    connector: str
    mcp_server: str
    status: ToolStatus
    risk_class: ToolRiskClass
    enabled: bool
    disabled_reason: str | None
    required_scopes: list[str]
    allowed_workflows: list[str]
    requires_approval: bool


class ToolDetail(ToolSummary):
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    source_path: str


class ToolRegistry:
    def __init__(self, tools: dict[str, ToolConfig], source_paths: dict[str, Path]) -> None:
        self._tools = tools
        self._source_paths = source_paths

    @classmethod
    def from_directory(cls, config_dir: Path) -> ToolRegistry:
        if not config_dir.exists():
            raise ToolRegistryError(f"tool config directory does not exist: {config_dir}")

        tools: dict[str, ToolConfig] = {}
        source_paths: dict[str, Path] = {}
        for config_path in sorted(config_dir.glob("*.yaml")):
            tool = load_tool_config(config_path)
            if tool.id in tools:
                raise ToolRegistryError(f"duplicate tool id: {tool.id}")
            tools[tool.id] = tool
            source_paths[tool.id] = config_path

        if not tools:
            raise ToolRegistryError(f"no tool configs found in {config_dir}")

        return cls(tools=tools, source_paths=source_paths)

    def list_tools(self, available_connectors: set[str] | None = None) -> list[ToolSummary]:
        connectors = available_connectors or set()
        return [
            tool_to_summary(tool, connectors)
            for tool in sorted(self._tools.values(), key=lambda item: item.id)
        ]

    def get_tool(
        self,
        tool_id: str,
        available_connectors: set[str] | None = None,
    ) -> ToolDetail:
        tool = self._tools.get(tool_id)
        if tool is None:
            raise ToolNotFoundError(tool_id)

        summary = tool_to_summary(tool, available_connectors or set())
        return ToolDetail(
            **summary.model_dump(),
            description=tool.description,
            input_schema=tool.input_schema.model_dump(mode="json"),
            output_schema=tool.output_schema.model_dump(mode="json"),
            source_path=str(self._source_paths[tool.id]),
        )


def load_tool_config(config_path: Path) -> ToolConfig:
    loaded = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ToolRegistryError(f"tool config must be a mapping: {config_path}")
    payload = cast(dict[str, Any], loaded)
    return ToolConfig.model_validate(payload)


def tool_to_summary(tool: ToolConfig, available_connectors: set[str]) -> ToolSummary:
    connector_ready = tool.connector in available_connectors
    enabled = tool.status == "contract_ready" and connector_ready
    disabled_reason = None
    if tool.status != "contract_ready":
        disabled_reason = f"tool status is {tool.status}"
    elif not connector_ready:
        disabled_reason = "required connector is not configured"

    return ToolSummary(
        id=tool.id,
        name=tool.name,
        connector=tool.connector,
        mcp_server=tool.mcp_server,
        status=tool.status,
        risk_class=tool.risk_class,
        enabled=enabled,
        disabled_reason=disabled_reason,
        required_scopes=tool.required_scopes,
        allowed_workflows=tool.allowed_workflows,
        requires_approval=tool.requires_approval,
    )


@lru_cache
def get_tool_registry(config_dir: str | None = None) -> ToolRegistry:
    resolved_config_dir = Path(config_dir) if config_dir is not None else DEFAULT_TOOL_CONFIG_DIR
    return ToolRegistry.from_directory(resolved_config_dir)
