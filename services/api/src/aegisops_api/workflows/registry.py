from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Literal, Self, cast

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from aegisops_api.config import Settings, get_settings

WorkflowStatus = Literal["planned", "ready", "gated", "disabled"]
AutonomyLevel = Literal["read_only", "draft_only", "approval_required", "autonomous"]

DEFAULT_WORKFLOW_CONFIG_DIR = Path(__file__).resolve().parents[5] / "configs" / "workflows"


class WorkflowRegistryError(RuntimeError):
    pass


class WorkflowNotFoundError(LookupError):
    pass


class EnabledWhen(BaseModel):
    connectors: list[str] = Field(min_length=1)
    required_scopes: list[str] = Field(default_factory=list)


class DataPolicy(BaseModel):
    fake_data_allowed: bool
    replay_allowed_from_real_runs: bool
    regex_business_extraction_allowed: bool

    @model_validator(mode="after")
    def validate_real_data_only(self) -> Self:
        if self.fake_data_allowed:
            raise ValueError("workflow configs must not allow fake data")
        if self.regex_business_extraction_allowed:
            raise ValueError("workflow configs must not allow regex business extraction")
        return self


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


class WorkflowRegistry:
    def __init__(self, workflows: dict[str, WorkflowConfig], source_paths: dict[str, Path]) -> None:
        self._workflows = workflows
        self._source_paths = source_paths

    @classmethod
    def from_directory(cls, config_dir: Path) -> WorkflowRegistry:
        if not config_dir.exists():
            raise WorkflowRegistryError(f"workflow config directory does not exist: {config_dir}")

        workflows: dict[str, WorkflowConfig] = {}
        source_paths: dict[str, Path] = {}
        for config_path in sorted(config_dir.glob("*.yaml")):
            workflow = load_workflow_config(config_path)
            if workflow.id in workflows:
                raise WorkflowRegistryError(f"duplicate workflow id: {workflow.id}")
            workflows[workflow.id] = workflow
            source_paths[workflow.id] = config_path

        if not workflows:
            raise WorkflowRegistryError(f"no workflow configs found in {config_dir}")

        return cls(workflows=workflows, source_paths=source_paths)

    def list_workflows(self, available_connectors: set[str] | None = None) -> list[WorkflowSummary]:
        connectors = available_connectors or set()
        return [
            workflow_to_summary(workflow, connectors)
            for workflow in sorted(self._workflows.values(), key=lambda item: item.id)
        ]

    def get_workflow(
        self,
        workflow_id: str,
        available_connectors: set[str] | None = None,
    ) -> WorkflowDetail:
        workflow = self._workflows.get(workflow_id)
        if workflow is None:
            raise WorkflowNotFoundError(workflow_id)

        summary = workflow_to_summary(workflow, available_connectors or set())
        return WorkflowDetail(
            **summary.model_dump(),
            data_policy=workflow.data_policy,
            approval_required_for=workflow.approval_required_for,
            visual_surfaces=workflow.visual_surfaces,
            source_path=str(self._source_paths[workflow.id]),
        )


def load_workflow_config(config_path: Path) -> WorkflowConfig:
    loaded = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise WorkflowRegistryError(f"workflow config must be a mapping: {config_path}")
    payload = cast(dict[str, Any], loaded)
    return WorkflowConfig.model_validate(payload)


def workflow_to_summary(
    workflow: WorkflowConfig,
    available_connectors: set[str],
) -> WorkflowSummary:
    required_connectors = workflow.enabled_when.connectors
    missing_connectors = sorted(set(required_connectors) - available_connectors)
    enabled = workflow.status == "ready" and not missing_connectors
    disabled_reason = None
    if workflow.status != "ready":
        disabled_reason = f"workflow status is {workflow.status}"
    elif missing_connectors:
        disabled_reason = "required connectors are not configured"

    return WorkflowSummary(
        id=workflow.id,
        name=workflow.name,
        domain=workflow.domain,
        status=workflow.status,
        enabled=enabled,
        disabled_reason=disabled_reason,
        required_connectors=required_connectors,
        missing_connectors=missing_connectors,
        required_scopes=workflow.enabled_when.required_scopes,
        default_autonomy=workflow.default_autonomy,
        patterns=workflow.patterns,
    )


def get_workflow_config_dir(settings: Settings | None = None) -> Path:
    resolved_settings = settings or get_settings()
    return resolved_settings.workflow_config_dir or DEFAULT_WORKFLOW_CONFIG_DIR


def get_available_connectors(settings: Settings | None = None) -> set[str]:
    resolved_settings = settings or get_settings()
    return {
        connector.strip()
        for connector in resolved_settings.configured_connectors.split(",")
        if connector.strip()
    }


@lru_cache
def get_workflow_registry(config_dir: str | None = None) -> WorkflowRegistry:
    resolved_config_dir = Path(config_dir) if config_dir is not None else get_workflow_config_dir()
    return WorkflowRegistry.from_directory(resolved_config_dir)
