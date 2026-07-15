from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from aegisops_api.config import Settings, get_settings
from aegisops_api.workflows.incident_response_investigator.graph import (
    INCIDENT_WORKFLOW_ID,
    IncidentInvestigationState,
    IncidentTimeWindow,
)
from aegisops_api.workflows.registry import AutonomyLevel

DEFAULT_INCIDENT_REPLAY_FIXTURE_DIR = (
    Path(__file__).resolve().parents[6]
    / "configs"
    / "replays"
    / "incident_response_investigator"
)


class ReplayFixtureError(RuntimeError):
    def __init__(self, reason_code: str, message: str, http_status: int = 422) -> None:
        super().__init__(message)
        self.reason_code = reason_code
        self.message = message
        self.http_status = http_status


class ReplayDataPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fake_data_allowed: Literal[False]
    replay_allowed_from_real_runs: Literal[True]


class GitHubFileReplayPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    ref: str
    content: str
    sha: str


class IncidentReplayFixture(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["incident_response_investigator.replay.v1"]
    workflow_id: Literal["incident_response_investigator"]
    provenance: Literal["captured_real_run"]
    source_run_id: str = Field(min_length=1)
    captured_at: datetime
    incident_id: str = Field(min_length=1)
    service: str = Field(min_length=1)
    time_window: IncidentTimeWindow
    severity: str | None = Field(default=None, min_length=1)
    environment: str | None = Field(default=None, min_length=1)
    repository: str | None = Field(default=None, min_length=1)
    ref: str = Field(default="main", min_length=1)
    suspect_paths: list[str] = Field(default_factory=list, max_length=10)
    log_events: list[dict[str, Any]] = Field(default_factory=list)
    deployment_events: list[dict[str, Any]] = Field(default_factory=list)
    code_files: list[GitHubFileReplayPayload] = Field(default_factory=list, max_length=10)
    log_tool_call_ids: list[str] = Field(default_factory=list)
    deployment_tool_call_ids: list[str] = Field(default_factory=list)
    code_tool_call_ids: list[str] = Field(default_factory=list)
    log_policy_decision_ids: list[str] = Field(default_factory=list)
    deployment_policy_decision_ids: list[str] = Field(default_factory=list)
    code_policy_decision_ids: list[str] = Field(default_factory=list)
    data_policy: ReplayDataPolicy

    @model_validator(mode="after")
    def validate_real_replay_policy(self) -> IncidentReplayFixture:
        if self.data_policy.fake_data_allowed:
            raise ValueError("replay fixtures must not allow fake data")
        if not self.data_policy.replay_allowed_from_real_runs:
            raise ValueError("replay fixtures must come from replay-allowed real runs")
        if self.suspect_paths and self.repository is None:
            raise ValueError("repository is required when suspect_paths are captured")
        return self

    def to_graph_state(
        self,
        run_id: UUID,
        autonomy_level: AutonomyLevel,
        actor_id: str | None,
        trace_id: str | None,
    ) -> IncidentInvestigationState:
        return {
            "run_id": run_id,
            "workflow_id": INCIDENT_WORKFLOW_ID,
            "incident_id": self.incident_id,
            "service": self.service,
            "time_window": self.time_window.to_tool_payload(),
            "severity": self.severity,
            "environment": self.environment,
            "repository": self.repository,
            "ref": self.ref,
            "suspect_paths": self.suspect_paths,
            "autonomy_level": autonomy_level,
            "actor_id": actor_id,
            "trace_id": trace_id,
            "log_events": self.log_events,
            "deployment_events": self.deployment_events,
            "code_files": [
                file_payload.model_dump(mode="json") for file_payload in self.code_files
            ],
            "log_tool_call_ids": self.log_tool_call_ids,
            "deployment_tool_call_ids": self.deployment_tool_call_ids,
            "code_tool_call_ids": self.code_tool_call_ids,
            "log_policy_decision_ids": self.log_policy_decision_ids,
            "deployment_policy_decision_ids": self.deployment_policy_decision_ids,
            "code_policy_decision_ids": self.code_policy_decision_ids,
            "evidence": [],
        }


def get_incident_replay_fixture_dir(settings: Settings | None = None) -> Path:
    resolved_settings = settings or get_settings()
    return resolved_settings.replay_fixture_dir or DEFAULT_INCIDENT_REPLAY_FIXTURE_DIR


def load_incident_replay_fixture(
    source_run_id: str,
    fixture_dir: Path | None = None,
) -> IncidentReplayFixture:
    fixture_path = get_replay_fixture_path(source_run_id, fixture_dir)
    if not fixture_path.exists():
        raise ReplayFixtureError(
            reason_code="replay_fixture_not_found",
            message=f"Replay fixture was not found for source run {source_run_id}.",
            http_status=404,
        )
    loaded = json.loads(fixture_path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ReplayFixtureError(
            reason_code="replay_fixture_invalid",
            message="Replay fixture root must be a JSON object.",
        )
    try:
        return IncidentReplayFixture.model_validate(loaded)
    except ValueError as exc:
        raise ReplayFixtureError(
            reason_code="replay_fixture_invalid",
            message=str(exc),
        ) from exc


def get_replay_fixture_path(source_run_id: str, fixture_dir: Path | None = None) -> Path:
    if not is_safe_source_run_id(source_run_id):
        raise ReplayFixtureError(
            reason_code="replay_source_run_id_invalid",
            message="Replay source run id must be a single file-safe identifier.",
        )
    base_dir = fixture_dir or get_incident_replay_fixture_dir()
    return base_dir / f"{source_run_id}.json"


def is_safe_source_run_id(source_run_id: str) -> bool:
    if not source_run_id or source_run_id in {".", ".."}:
        return False
    path = Path(source_run_id)
    if path.name != source_run_id:
        return False
    return not any(character in source_run_id for character in {"/", "\\", ":"})
