from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any, Literal, Protocol, cast
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from aegisops_api.audit import AuditEventInput, write_audit_event
from aegisops_api.config import Settings, get_settings
from aegisops_api.db.models import WorkflowRun, utc_now
from aegisops_api.db.session import get_session_factory
from aegisops_api.policy import PolicyDecision
from aegisops_api.tools.adapters import create_default_tool_adapter_registry
from aegisops_api.tools.registry import get_tool_registry
from aegisops_api.workflows.engineering_issue_to_pr.replay import (
    ReplayFixtureError as EngineeringReplayFixtureError,
)
from aegisops_api.workflows.engineering_issue_to_pr.replay import (
    load_issue_to_pr_replay_fixture,
)
from aegisops_api.workflows.engineering_issue_to_pr.runtime import (
    IssueToPrRunRequest,
    collect_engineering_issue_context,
)
from aegisops_api.workflows.incident_response_investigator.replay import (
    ReplayFixtureError as IncidentReplayFixtureError,
)
from aegisops_api.workflows.incident_response_investigator.replay import (
    load_incident_replay_fixture,
)
from aegisops_api.workflows.incident_response_investigator.runtime import (
    IncidentInvestigationRequest,
    collect_incident_evidence,
)
from aegisops_api.workflows.registry import WorkflowRegistry, get_workflow_registry
from aegisops_api.workflows.runs import BudgetEnvelope, get_or_create_registry_snapshot

DemoSeedWorkflowId = Literal["engineering_issue_to_pr", "incident_response_investigator"]


class DemoSeedError(RuntimeError):
    def __init__(self, reason_code: str, message: str, http_status: int = 422) -> None:
        super().__init__(message)
        self.reason_code = reason_code
        self.message = message
        self.http_status = http_status


class DemoSeedRunSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    workflow_id: DemoSeedWorkflowId
    source_run_id: str = Field(min_length=1)
    actor_id: str | None = None
    trace_id: str | None = None
    include_rca: bool = False


class DemoSeedManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["aegisops.demo_seed_manifest.v1"]
    provenance: Literal["captured_real_run_manifest"]
    reset_existing_seeded_runs: bool = True
    runs: list[DemoSeedRunSpec] = Field(min_length=1, max_length=20)


class DemoSeededRun(BaseModel):
    run_id: UUID
    workflow_id: DemoSeedWorkflowId
    source_run_id: str
    status: str
    evidence_count: int
    reset_count: int


class DemoSeedResult(BaseModel):
    schema_version: Literal["aegisops.demo_seed_result.v1"] = "aegisops.demo_seed_result.v1"
    seeded_runs: list[DemoSeededRun]


class ToolPolicyEvaluator(Protocol):
    async def evaluate(self, input_payload: dict[str, Any]) -> PolicyDecision:
        pass


class ReplaySeedToolPolicyEvaluator:
    async def evaluate(self, input_payload: dict[str, Any]) -> PolicyDecision:
        return PolicyDecision(
            package_path="aegisops.tool_access",
            allowed=True,
            requires_approval=False,
            decision_id="demo-seed-replay-policy",
            reason_codes=[],
            result={"allow": True, "requires_approval": False, "reason_codes": []},
        )


def load_demo_seed_manifest(path: Path) -> DemoSeedManifest:
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DemoSeedError(
            reason_code="demo_seed_manifest_invalid",
            message=f"Demo seed manifest is not valid JSON: {exc.msg}.",
        ) from exc
    if not isinstance(loaded, dict):
        raise DemoSeedError(
            reason_code="demo_seed_manifest_invalid",
            message="Demo seed manifest root must be a JSON object.",
        )
    try:
        return DemoSeedManifest.model_validate(loaded)
    except ValidationError as exc:
        raise DemoSeedError(
            reason_code="demo_seed_manifest_invalid",
            message=str(exc),
        ) from exc


async def seed_demo_replay_runs(
    manifest: DemoSeedManifest,
    session: Session,
    settings: Settings | None = None,
    workflow_registry: WorkflowRegistry | None = None,
) -> DemoSeedResult:
    resolved_settings = settings or get_settings()
    registry = workflow_registry or get_workflow_registry()
    tool_registry = get_tool_registry()
    adapter_registry = create_default_tool_adapter_registry()
    policy_evaluator = ReplaySeedToolPolicyEvaluator()
    seeded_runs: list[DemoSeededRun] = []

    for run_spec in manifest.runs:
        fixture_dir = replay_fixture_dir_for_workflow(run_spec.workflow_id, resolved_settings)
        validate_captured_replay_fixture(run_spec, fixture_dir)
        reset_count = (
            reset_existing_seeded_runs(session, run_spec)
            if manifest.reset_existing_seeded_runs
            else 0
        )
        run = create_seeded_workflow_run(
            session=session,
            run_spec=run_spec,
            manifest=manifest,
            workflow_registry=registry,
            settings=resolved_settings,
        )
        if run_spec.workflow_id == "engineering_issue_to_pr":
            engineering_response = await collect_engineering_issue_context(
                run_id=run.id,
                request=IssueToPrRunRequest(actor_id=run_spec.actor_id, trace_id=run_spec.trace_id),
                session=session,
                workflow_registry=registry,
                tool_registry=tool_registry,
                policy_evaluator=policy_evaluator,
                adapter_registry=adapter_registry,
                available_connectors=set(),
                replay_fixture_dir=fixture_dir,
            )
            evidence_count = len(engineering_response.evidence_records)
        else:
            incident_response = await collect_incident_evidence(
                run_id=run.id,
                request=IncidentInvestigationRequest(
                    actor_id=run_spec.actor_id,
                    trace_id=run_spec.trace_id,
                    include_rca=run_spec.include_rca,
                ),
                session=session,
                workflow_registry=registry,
                tool_registry=tool_registry,
                policy_evaluator=policy_evaluator,
                adapter_registry=adapter_registry,
                available_connectors=set(),
                replay_fixture_dir=fixture_dir,
            )
            evidence_count = len(incident_response.evidence_records)
        mark_seeded_run_complete(session, run, evidence_count)
        seeded_runs.append(
            DemoSeededRun(
                run_id=run.id,
                workflow_id=run_spec.workflow_id,
                source_run_id=run_spec.source_run_id,
                status=run.status,
                evidence_count=evidence_count,
                reset_count=reset_count,
            )
        )

    return DemoSeedResult(seeded_runs=seeded_runs)


def create_seeded_workflow_run(
    *,
    session: Session,
    run_spec: DemoSeedRunSpec,
    manifest: DemoSeedManifest,
    workflow_registry: WorkflowRegistry,
    settings: Settings,
) -> WorkflowRun:
    workflow = workflow_registry.get_workflow(
        run_spec.workflow_id,
        available_connectors=set(),
    )
    snapshot = get_or_create_registry_snapshot(session, workflow)
    seeded_at = utc_now()
    run = WorkflowRun(
        id=uuid4(),
        workflow_id=workflow.id,
        registry_snapshot_id=snapshot.id,
        status="queued",
        execution_mode="replay",
        autonomy_level=workflow.default_autonomy,
        input_payload={
            "replay_source_run_id": run_spec.source_run_id,
            "demo_seed": True,
        },
        budget=BudgetEnvelope.from_settings(settings).model_dump(mode="json"),
        policy_context={
            "demo_seed": {
                "schema_version": manifest.schema_version,
                "provenance": manifest.provenance,
                "source_run_id": run_spec.source_run_id,
                "seeded_at": seeded_at.isoformat(),
            }
        },
        started_at=seeded_at,
        updated_at=seeded_at,
    )
    session.add(run)
    session.flush()
    write_audit_event(
        session,
        AuditEventInput(
            run_id=run.id,
            workflow_id=run.workflow_id,
            event_type="demo_seed.run_created",
            actor_type="system",
            action="demo_seed.create_replay_run",
            resource_type="workflow_run",
            resource_id=str(run.id),
            trace_id=run_spec.trace_id,
            payload={
                "workflow_id": run_spec.workflow_id,
                "source_run_id": run_spec.source_run_id,
                "provenance": manifest.provenance,
            },
        ),
    )
    session.commit()
    return run


def reset_existing_seeded_runs(session: Session, run_spec: DemoSeedRunSpec) -> int:
    candidates = session.execute(
        select(WorkflowRun).where(
            WorkflowRun.workflow_id == run_spec.workflow_id,
            WorkflowRun.execution_mode == "replay",
        )
    ).scalars()
    reset_count = 0
    for run in candidates:
        marker = (run.policy_context or {}).get("demo_seed")
        if not isinstance(marker, dict):
            continue
        if marker.get("source_run_id") != run_spec.source_run_id:
            continue
        session.delete(run)
        reset_count += 1
    if reset_count:
        session.flush()
        session.commit()
    return reset_count


def mark_seeded_run_complete(session: Session, run: WorkflowRun, evidence_count: int) -> None:
    completed_at = utc_now()
    run.status = "completed"
    run.completed_at = completed_at
    run.updated_at = completed_at
    write_audit_event(
        session,
        AuditEventInput(
            run_id=run.id,
            workflow_id=run.workflow_id,
            event_type="demo_seed.completed",
            actor_type="system",
            action="demo_seed.persist_replay_trace",
            resource_type="workflow_run",
            resource_id=str(run.id),
            payload={"evidence_count": evidence_count},
        ),
    )
    session.commit()


def validate_captured_replay_fixture(
    run_spec: DemoSeedRunSpec,
    fixture_dir: Path | None,
) -> None:
    try:
        if run_spec.workflow_id == "engineering_issue_to_pr":
            fixture_source_run_id = load_issue_to_pr_replay_fixture(
                run_spec.source_run_id,
                fixture_dir,
            ).source_run_id
        else:
            fixture_source_run_id = load_incident_replay_fixture(
                run_spec.source_run_id,
                fixture_dir,
            ).source_run_id
    except (EngineeringReplayFixtureError, IncidentReplayFixtureError) as exc:
        raise DemoSeedError(exc.reason_code, exc.message, exc.http_status) from exc

    if fixture_source_run_id != run_spec.source_run_id:
        raise DemoSeedError(
            reason_code="demo_seed_fixture_source_mismatch",
            message="Replay fixture source_run_id must match the demo seed manifest.",
        )


def replay_fixture_dir_for_workflow(
    workflow_id: DemoSeedWorkflowId,
    settings: Settings,
) -> Path | None:
    if settings.replay_fixture_dir is None:
        return None
    workflow_specific_dir = settings.replay_fixture_dir / workflow_id
    if workflow_specific_dir.exists():
        return workflow_specific_dir
    return settings.replay_fixture_dir


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Seed demo replay runs from captured-real-run fixtures only.",
    )
    parser.add_argument("manifest", type=Path, help="Path to demo seed manifest JSON.")
    parser.add_argument("--database-url", default=None, help="Override DATABASE_URL.")
    parser.add_argument(
        "--no-reset",
        action="store_true",
        help="Do not remove prior demo-seeded runs for the same captured source ids.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    manifest = load_demo_seed_manifest(cast(Path, args.manifest))
    if args.no_reset:
        manifest = manifest.model_copy(update={"reset_existing_seeded_runs": False})

    session = get_session_factory(cast(str | None, args.database_url))()
    try:
        result = asyncio.run(seed_demo_replay_runs(manifest=manifest, session=session))
        print(result.model_dump_json(indent=2))
    finally:
        session.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
