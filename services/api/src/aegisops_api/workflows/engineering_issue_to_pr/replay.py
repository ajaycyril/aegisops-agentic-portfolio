from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from aegisops_api.config import Settings, get_settings
from aegisops_api.workflows.engineering_issue_to_pr.graph import (
    ENGINEERING_WORKFLOW_ID,
    IssueToPrState,
)
from aegisops_api.workflows.registry import AutonomyLevel

DEFAULT_ENGINEERING_REPLAY_FIXTURE_DIR = (
    Path(__file__).resolve().parents[6] / "configs" / "replays" / "engineering_issue_to_pr"
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


class GitHubIssueReplayPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    body: str
    labels: list[str] = Field(default_factory=list)
    author: str
    url: str


class GitHubFileReplayPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    ref: str
    content: str
    sha: str


class IssueToPrReplayFixture(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["engineering_issue_to_pr.replay.v1"]
    workflow_id: Literal["engineering_issue_to_pr"]
    provenance: Literal["captured_real_run"]
    source_run_id: str = Field(min_length=1)
    captured_at: datetime
    repository: str = Field(min_length=1)
    issue_number: int = Field(gt=0)
    ref: str = Field(default="main", min_length=1)
    issue: GitHubIssueReplayPayload
    context_files: list[GitHubFileReplayPayload] = Field(default_factory=list, max_length=10)
    tool_call_ids: list[str] = Field(default_factory=list)
    policy_decision_ids: list[str] = Field(default_factory=list)
    data_policy: ReplayDataPolicy

    @model_validator(mode="after")
    def validate_real_replay_policy(self) -> IssueToPrReplayFixture:
        if self.data_policy.fake_data_allowed:
            raise ValueError("replay fixtures must not allow fake data")
        if not self.data_policy.replay_allowed_from_real_runs:
            raise ValueError("replay fixtures must come from replay-allowed real runs")
        return self

    def to_graph_state(
        self,
        run_id: UUID,
        autonomy_level: AutonomyLevel,
        actor_id: str | None,
        trace_id: str | None,
    ) -> IssueToPrState:
        return {
            "run_id": run_id,
            "workflow_id": ENGINEERING_WORKFLOW_ID,
            "repository": self.repository,
            "issue_number": self.issue_number,
            "ref": self.ref,
            "context_paths": [file_payload.path for file_payload in self.context_files],
            "autonomy_level": autonomy_level,
            "actor_id": actor_id,
            "trace_id": trace_id,
            "issue": self.issue.model_dump(mode="json"),
            "context_files": [
                file_payload.model_dump(mode="json") for file_payload in self.context_files
            ],
            "tool_call_ids": self.tool_call_ids,
            "policy_decision_ids": self.policy_decision_ids,
            "evidence": [],
        }


def get_engineering_replay_fixture_dir(settings: Settings | None = None) -> Path:
    resolved_settings = settings or get_settings()
    return resolved_settings.replay_fixture_dir or DEFAULT_ENGINEERING_REPLAY_FIXTURE_DIR


def load_issue_to_pr_replay_fixture(
    source_run_id: str,
    fixture_dir: Path | None = None,
) -> IssueToPrReplayFixture:
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
        return IssueToPrReplayFixture.model_validate(loaded)
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
    base_dir = fixture_dir or get_engineering_replay_fixture_dir()
    return base_dir / f"{source_run_id}.json"


def is_safe_source_run_id(source_run_id: str) -> bool:
    if not source_run_id or source_run_id in {".", ".."}:
        return False
    path = Path(source_run_id)
    if path.name != source_run_id:
        return False
    return not any(character in source_run_id for character in {"/", "\\", ":"})
