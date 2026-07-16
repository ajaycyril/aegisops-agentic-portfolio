from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal, Self, cast

import yaml
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, model_validator

ROOT_DIR = Path(__file__).resolve().parent
CONFIG_DIR = ROOT_DIR / "configs"

WorkflowStatus = Literal["planned", "ready", "gated", "disabled"]
AutonomyLevel = Literal["read_only", "draft_only", "approval_required", "autonomous"]
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
ToolRiskClass = Literal["read", "draft", "write", "external_message", "financial", "access_change"]
ToolStatus = Literal["contract_ready", "planned", "disabled"]


class EnabledWhen(BaseModel):
    connectors: list[str] = Field(min_length=1)
    required_scopes: list[str] = Field(default_factory=list)


class DataPolicy(BaseModel):
    fake_data_allowed: bool
    replay_allowed_from_real_runs: bool
    regex_business_extraction_allowed: bool


class WorkflowConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    domain: str
    status: WorkflowStatus
    enabled_when: EnabledWhen
    patterns: list[str] = Field(min_length=1)
    data_policy: DataPolicy
    default_autonomy: AutonomyLevel
    approval_required_for: list[str] = Field(default_factory=list)
    visual_surfaces: list[str] = Field(default_factory=list)


class WorkflowSummary(BaseModel):
    id: str
    name: str
    domain: str
    status: WorkflowStatus
    enabled: bool
    disabled_reason: str | None
    required_connectors: list[str]
    missing_connectors: list[str]
    required_scopes: list[str]
    default_autonomy: AutonomyLevel
    patterns: list[str]


class WorkflowDetail(WorkflowSummary):
    data_policy: DataPolicy
    approval_required_for: list[str]
    visual_surfaces: list[str]
    source_path: str


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

    @property
    def requires_approval(self) -> bool:
        return self.approval_required is True or self.risk_class in {
            "write",
            "external_message",
            "financial",
            "access_change",
        }


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


app = FastAPI(
    title="AegisOps Read-Only API",
    version="0.1.0",
    summary="Read-only public registry gateway for the AegisOps portfolio.",
)


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "aegisops-api", "mode": "vercel_readonly"}


@app.get("/ready", tags=["system"])
async def ready() -> dict[str, object]:
    try:
        registry_counts = config_counts()
    except ConfigSnapshotError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    return {
        "status": "ready",
        "environment": os.environ.get("APP_ENV", "production"),
        "mode": "vercel_readonly",
        "registry_configured": True,
        "registry_counts": registry_counts,
        "policy_configured": False,
        "database_configured": False,
        "live_runs_require_approval": True,
        "live_run_admin_gate_configured": False,
        "engineering_issue_to_pr_planner_configured": False,
        "openai_planner_model": None,
    }


@app.get("/version", tags=["system"])
async def version() -> dict[str, str]:
    return {"version": "0.1.0", "mode": "vercel_readonly"}


@app.get("/workflows", response_model=list[WorkflowSummary], tags=["workflows"])
async def list_workflows() -> list[WorkflowSummary]:
    connectors = configured_connectors()
    return [workflow_summary(workflow, connectors) for workflow in workflow_configs()]


@app.get("/workflows/{workflow_id}", response_model=WorkflowDetail, tags=["workflows"])
async def get_workflow(workflow_id: str) -> WorkflowDetail:
    connectors = configured_connectors()
    for workflow, source_path in workflow_config_items():
        if workflow.id == workflow_id:
            summary = workflow_summary(workflow, connectors)
            return WorkflowDetail(
                **summary.model_dump(),
                data_policy=workflow.data_policy,
                approval_required_for=workflow.approval_required_for,
                visual_surfaces=workflow.visual_surfaces,
                source_path=str(source_path),
            )
    raise HTTPException(status_code=404, detail="workflow not found")


@app.get("/connectors", response_model=list[ConnectorSummary], tags=["connectors"])
async def list_connectors() -> list[ConnectorSummary]:
    configured = configured_connectors()
    return [connector_summary(connector, configured) for connector in connector_configs()]


@app.get("/connectors/{connector_id}", response_model=ConnectorDetail, tags=["connectors"])
async def get_connector(connector_id: str) -> ConnectorDetail:
    configured = configured_connectors()
    for connector, source_path in connector_config_items():
        if connector.id == connector_id:
            summary = connector_summary(connector, configured)
            return ConnectorDetail(
                **summary.model_dump(),
                tool_ids=connector.tool_ids,
                workflow_ids=connector.workflow_ids,
                data_boundaries=connector.data_boundaries,
                source_path=str(source_path),
            )
    raise HTTPException(status_code=404, detail="connector not found")


@app.get("/tools", response_model=list[ToolSummary], tags=["tools"])
async def list_tools() -> list[ToolSummary]:
    connectors = configured_connectors()
    return [tool_summary(tool, connectors) for tool in tool_configs()]


@app.get("/tools/{tool_id}", response_model=ToolDetail, tags=["tools"])
async def get_tool(tool_id: str) -> ToolDetail:
    connectors = configured_connectors()
    for tool, source_path in tool_config_items():
        if tool.id == tool_id:
            summary = tool_summary(tool, connectors)
            return ToolDetail(
                **summary.model_dump(),
                description=tool.description,
                input_schema=tool.input_schema.model_dump(mode="json"),
                output_schema=tool.output_schema.model_dump(mode="json"),
                source_path=str(source_path),
            )
    raise HTTPException(status_code=404, detail="tool not found")


def workflow_summary(workflow: WorkflowConfig, connectors: set[str]) -> WorkflowSummary:
    required = workflow.enabled_when.connectors
    missing = sorted(set(required) - connectors)
    enabled = workflow.status == "ready" and not missing
    disabled_reason = None
    if workflow.status != "ready":
        disabled_reason = f"workflow status is {workflow.status}"
    elif missing:
        disabled_reason = "required connectors are not configured"
    return WorkflowSummary(
        id=workflow.id,
        name=workflow.name,
        domain=workflow.domain,
        status=workflow.status,
        enabled=enabled,
        disabled_reason=disabled_reason,
        required_connectors=required,
        missing_connectors=missing,
        required_scopes=workflow.enabled_when.required_scopes,
        default_autonomy=workflow.default_autonomy,
        patterns=workflow.patterns,
    )


def connector_summary(connector: ConnectorConfig, configured: set[str]) -> ConnectorSummary:
    deployment_enabled = connector.id in configured
    missing_env_vars = [
        env_var for env_var in connector.required_env_vars if not os.environ.get(env_var)
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


def tool_summary(tool: ToolConfig, connectors: set[str]) -> ToolSummary:
    connector_ready = tool.connector in connectors
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


def configured_connectors() -> set[str]:
    return {
        connector.strip()
        for connector in os.environ.get("CONFIGURED_CONNECTORS", "").split(",")
        if connector.strip()
    }


class ConfigSnapshotError(RuntimeError):
    pass


def config_counts() -> dict[str, int]:
    return {
        "workflows": len(workflow_configs()),
        "connectors": len(connector_configs()),
        "tools": len(tool_configs()),
    }


@lru_cache
def workflow_configs() -> tuple[WorkflowConfig, ...]:
    return tuple(workflow for workflow, _ in workflow_config_items())


@lru_cache
def connector_configs() -> tuple[ConnectorConfig, ...]:
    return tuple(connector for connector, _ in connector_config_items())


@lru_cache
def tool_configs() -> tuple[ToolConfig, ...]:
    return tuple(tool for tool, _ in tool_config_items())


@lru_cache
def workflow_config_items() -> tuple[tuple[WorkflowConfig, Path], ...]:
    return tuple(
        (WorkflowConfig.model_validate(load_yaml(path)), path)
        for path in config_paths("workflows")
    )


@lru_cache
def connector_config_items() -> tuple[tuple[ConnectorConfig, Path], ...]:
    return tuple(
        (ConnectorConfig.model_validate(load_yaml(path)), path)
        for path in config_paths("connectors")
    )


@lru_cache
def tool_config_items() -> tuple[tuple[ToolConfig, Path], ...]:
    return tuple(
        (ToolConfig.model_validate(load_yaml(path)), path)
        for path in config_paths("tools")
    )


def config_paths(kind: str) -> tuple[Path, ...]:
    directory = CONFIG_DIR / kind
    if not directory.exists():
        raise ConfigSnapshotError(f"registry config directory is missing: {directory}")
    paths = tuple(sorted(directory.glob("*.yaml")))
    if not paths:
        raise ConfigSnapshotError(f"registry config directory has no YAML files: {directory}")
    return paths


def load_yaml(path: Path) -> dict[str, Any]:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise RuntimeError(f"expected YAML mapping in {path}")
    return cast(dict[str, Any], loaded)
