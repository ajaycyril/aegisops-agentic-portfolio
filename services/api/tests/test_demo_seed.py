import json
from pathlib import Path
from typing import Any, cast

import pytest
from sqlalchemy.orm import Session

from aegisops_api.config import Settings
from aegisops_api.db.models import AuditEvent, WorkflowRegistrySnapshot, WorkflowRun
from aegisops_api.demo_seed import (
    DemoSeedError,
    DemoSeedManifest,
    DemoSeedRunSpec,
    create_seeded_workflow_run,
    load_demo_seed_manifest,
    validate_captured_replay_fixture,
)
from aegisops_api.workflows.registry import WorkflowRegistry


class EmptySnapshotResult:
    def scalar_one_or_none(self) -> object | None:
        return None


class RecordingSession:
    def __init__(self) -> None:
        self.added: list[object] = []
        self.flush_count = 0
        self.commit_count = 0

    def execute(self, _statement: object) -> EmptySnapshotResult:
        return EmptySnapshotResult()

    def add(self, instance: object) -> None:
        self.added.append(instance)

    def flush(self) -> None:
        self.flush_count += 1

    def commit(self) -> None:
        self.commit_count += 1


def create_registry(tmp_path: Path) -> WorkflowRegistry:
    config_path = tmp_path / "engineering_issue_to_pr.yaml"
    config_path.write_text(
        "\n".join(
            [
                "id: engineering_issue_to_pr",
                "name: Engineering Replay Seed",
                "domain: engineering",
                "status: planned",
                "enabled_when:",
                "  connectors: [github]",
                "  required_scopes: [issues:read]",
                "patterns: [plan_execute]",
                "data_policy:",
                "  fake_data_allowed: false",
                "  replay_allowed_from_real_runs: true",
                "  regex_business_extraction_allowed: false",
                "default_autonomy: draft_only",
                "approval_required_for: [pull_request_creation]",
                "visual_surfaces: [trace_timeline]",
            ]
        ),
        encoding="utf-8",
    )
    return WorkflowRegistry.from_directory(tmp_path)


def test_load_demo_seed_manifest_requires_captured_real_run_manifest(tmp_path: Path) -> None:
    manifest_path = tmp_path / "demo-seed.json"
    manifest_path.write_text(
        """
        {
          "schema_version": "aegisops.demo_seed_manifest.v1",
          "provenance": "captured_real_run_manifest",
          "runs": [
            {
              "workflow_id": "engineering_issue_to_pr",
              "source_run_id": "captured-real-run-001"
            }
          ]
        }
        """,
        encoding="utf-8",
    )

    manifest = load_demo_seed_manifest(manifest_path)

    assert manifest.provenance == "captured_real_run_manifest"
    assert manifest.reset_existing_seeded_runs is True
    assert manifest.runs[0].source_run_id == "captured-real-run-001"


def test_validate_captured_replay_fixture_rejects_source_mismatch(tmp_path: Path) -> None:
    fixture_path = tmp_path / "captured-real-run-001.json"
    write_engineering_fixture(fixture_path, source_run_id="different-real-run")

    with pytest.raises(DemoSeedError) as exc_info:
        validate_captured_replay_fixture(
            DemoSeedRunSpec(
                workflow_id="engineering_issue_to_pr",
                source_run_id="captured-real-run-001",
            ),
            tmp_path,
        )

    assert exc_info.value.reason_code == "demo_seed_fixture_source_mismatch"


def test_create_seeded_workflow_run_marks_replay_policy_context(tmp_path: Path) -> None:
    session = RecordingSession()
    manifest = DemoSeedManifest(
        schema_version="aegisops.demo_seed_manifest.v1",
        provenance="captured_real_run_manifest",
        runs=[
            DemoSeedRunSpec(
                workflow_id="engineering_issue_to_pr",
                source_run_id="captured-real-run-001",
            )
        ],
    )

    run = create_seeded_workflow_run(
        session=cast(Session, session),
        run_spec=manifest.runs[0],
        manifest=manifest,
        workflow_registry=create_registry(tmp_path),
        settings=Settings(),
    )

    assert run.execution_mode == "replay"
    assert run.input_payload["replay_source_run_id"] == "captured-real-run-001"
    assert run.policy_context["demo_seed"]["provenance"] == "captured_real_run_manifest"
    assert any(isinstance(item, WorkflowRegistrySnapshot) for item in session.added)
    assert any(isinstance(item, WorkflowRun) for item in session.added)
    audit_event = next(item for item in session.added if isinstance(item, AuditEvent))
    assert audit_event.event_type == "demo_seed.run_created"
    assert session.commit_count == 1


def write_engineering_fixture(path: Path, source_run_id: str) -> None:
    payload: dict[str, Any] = {
        "schema_version": "engineering_issue_to_pr.replay.v1",
        "workflow_id": "engineering_issue_to_pr",
        "provenance": "captured_real_run",
        "source_run_id": source_run_id,
        "captured_at": "2026-07-14T00:00:00+00:00",
        "repository": "owner/repo",
        "issue_number": 12,
        "ref": "main",
        "issue": {
            "title": "Captured issue",
            "body": "Captured issue body",
            "labels": ["bug"],
            "author": "octocat",
            "url": "https://github.com/owner/repo/issues/12",
        },
        "context_files": [],
        "tool_call_ids": [],
        "policy_decision_ids": [],
        "data_policy": {
            "fake_data_allowed": False,
            "replay_allowed_from_real_runs": True,
        },
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
