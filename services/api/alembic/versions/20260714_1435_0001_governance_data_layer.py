"""Create governance data layer.

Revision ID: 0001_governance_data_layer
Revises:
Create Date: 2026-07-14 14:35:00.000000+00:00
"""

from collections.abc import Sequence

import pgvector.sqlalchemy
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001_governance_data_layer"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


RUN_STATUSES = ("queued", "running", "waiting_for_approval", "completed", "failed", "canceled")
APPROVAL_STATUSES = ("pending", "approved", "rejected", "expired", "canceled")
CALL_STATUSES = ("pending", "running", "succeeded", "failed", "blocked", "canceled")
EXECUTION_MODES = ("replay", "live")
TOOL_RISK_CLASSES = ("read", "draft", "write", "external_message", "financial", "access_change")
MEMORY_SCOPES = ("run", "workflow", "user", "org")
EVIDENCE_KINDS = (
    "document",
    "api_response",
    "log",
    "trace",
    "code",
    "human_input",
    "policy_decision",
)


def status_check(
    column_name: str,
    allowed_values: tuple[str, ...],
    name: str,
) -> sa.CheckConstraint:
    quoted_values = ", ".join(f"'{value}'" for value in allowed_values)
    return sa.CheckConstraint(f"{column_name} in ({quoted_values})", name=name)


def upgrade() -> None:
    op.execute(sa.text("CREATE EXTENSION IF NOT EXISTS vector"))

    op.create_table(
        "workflow_registry_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workflow_id", sa.String(length=120), nullable=False),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("source_path", sa.String(length=512), nullable=True),
        sa.Column("config_hash", sa.String(length=128), nullable=False),
        sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_by", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workflow_registry_snapshots")),
        sa.UniqueConstraint(
            "workflow_id",
            "version",
            name="uq_workflow_registry_snapshot_version",
        ),
    )
    op.create_index(
        "ix_workflow_registry_snapshots_workflow_active",
        "workflow_registry_snapshots",
        ["workflow_id", "is_active"],
    )

    op.create_table(
        "workflow_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workflow_id", sa.String(length=120), nullable=False),
        sa.Column("registry_snapshot_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("execution_mode", sa.String(length=24), nullable=False),
        sa.Column("autonomy_level", sa.String(length=64), nullable=False),
        sa.Column("org_id", sa.String(length=120), nullable=True),
        sa.Column("user_id", sa.String(length=120), nullable=True),
        sa.Column("input_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("budget", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("policy_context", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["registry_snapshot_id"],
            ["workflow_registry_snapshots.id"],
            name=op.f("fk_workflow_runs_registry_snapshot_id_workflow_registry_snapshots"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workflow_runs")),
        status_check("status", RUN_STATUSES, "workflow_run_status"),
        status_check("execution_mode", EXECUTION_MODES, "workflow_run_execution_mode"),
    )
    op.create_index("ix_workflow_runs_org_user", "workflow_runs", ["org_id", "user_id"])
    op.create_index("ix_workflow_runs_started_at", "workflow_runs", ["started_at"])
    op.create_index("ix_workflow_runs_workflow_status", "workflow_runs", ["workflow_id", "status"])

    op.create_table(
        "audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("workflow_id", sa.String(length=120), nullable=True),
        sa.Column("event_type", sa.String(length=120), nullable=False),
        sa.Column("actor_type", sa.String(length=64), nullable=False),
        sa.Column("actor_id", sa.String(length=120), nullable=True),
        sa.Column("action", sa.String(length=160), nullable=False),
        sa.Column("resource_type", sa.String(length=120), nullable=True),
        sa.Column("resource_id", sa.String(length=160), nullable=True),
        sa.Column("policy_decision_id", sa.String(length=160), nullable=True),
        sa.Column("trace_id", sa.String(length=160), nullable=True),
        sa.Column("data_sensitivity", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["workflow_runs.id"],
            name=op.f("fk_audit_events_run_id_workflow_runs"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_events")),
    )
    op.create_index("ix_audit_events_policy_decision", "audit_events", ["policy_decision_id"])
    op.create_index("ix_audit_events_run_created", "audit_events", ["run_id", "created_at"])
    op.create_index("ix_audit_events_trace", "audit_events", ["trace_id"])
    op.create_index(
        "ix_audit_events_workflow_created",
        "audit_events",
        ["workflow_id", "created_at"],
    )

    op.create_table(
        "approvals",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("risk_class", sa.String(length=32), nullable=False),
        sa.Column("requested_action", sa.String(length=160), nullable=False),
        sa.Column("requested_by", sa.String(length=120), nullable=False),
        sa.Column("approver_id", sa.String(length=120), nullable=True),
        sa.Column("request_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("decision_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("policy_decision_id", sa.String(length=160), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["workflow_runs.id"],
            name=op.f("fk_approvals_run_id_workflow_runs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_approvals")),
        status_check("status", APPROVAL_STATUSES, "approval_status"),
        status_check("risk_class", TOOL_RISK_CLASSES, "approval_risk_class"),
    )
    op.create_index("ix_approvals_requested_at", "approvals", ["requested_at"])
    op.create_index("ix_approvals_run_status", "approvals", ["run_id", "status"])

    op.create_table(
        "tool_calls",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("approval_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("tool_name", sa.String(length=160), nullable=False),
        sa.Column("tool_version", sa.String(length=64), nullable=False),
        sa.Column("risk_class", sa.String(length=32), nullable=False),
        sa.Column("input_schema_hash", sa.String(length=128), nullable=False),
        sa.Column("input_hash", sa.String(length=128), nullable=False),
        sa.Column("output_hash", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("policy_decision_id", sa.String(length=160), nullable=True),
        sa.Column("trace_id", sa.String(length=160), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("call_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["approval_id"],
            ["approvals.id"],
            name=op.f("fk_tool_calls_approval_id_approvals"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["workflow_runs.id"],
            name=op.f("fk_tool_calls_run_id_workflow_runs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tool_calls")),
        status_check("status", CALL_STATUSES, "tool_call_status"),
        status_check("risk_class", TOOL_RISK_CLASSES, "tool_call_risk_class"),
    )
    op.create_index("ix_tool_calls_policy_decision", "tool_calls", ["policy_decision_id"])
    op.create_index("ix_tool_calls_run_started", "tool_calls", ["run_id", "started_at"])
    op.create_index("ix_tool_calls_trace", "tool_calls", ["trace_id"])

    op.create_table(
        "model_calls",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(length=80), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=False),
        sa.Column("purpose", sa.String(length=120), nullable=False),
        sa.Column("prompt_version", sa.String(length=120), nullable=False),
        sa.Column("input_token_count", sa.BigInteger(), nullable=False),
        sa.Column("output_token_count", sa.BigInteger(), nullable=False),
        sa.Column("estimated_cost_usd", sa.Numeric(12, 6), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("trace_id", sa.String(length=160), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("policy_context", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("request_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("response_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["workflow_runs.id"],
            name=op.f("fk_model_calls_run_id_workflow_runs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_model_calls")),
        status_check("status", CALL_STATUSES, "model_call_status"),
    )
    op.create_index("ix_model_calls_model", "model_calls", ["provider", "model"])
    op.create_index("ix_model_calls_run_started", "model_calls", ["run_id", "started_at"])
    op.create_index("ix_model_calls_trace", "model_calls", ["trace_id"])

    op.create_table(
        "evidence_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workflow_id", sa.String(length=120), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("source_system", sa.String(length=120), nullable=False),
        sa.Column("source_uri", sa.Text(), nullable=True),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("content_hash", sa.String(length=128), nullable=False),
        sa.Column("evidence_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["workflow_runs.id"],
            name=op.f("fk_evidence_records_run_id_workflow_runs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_evidence_records")),
        status_check("kind", EVIDENCE_KINDS, "evidence_kind"),
    )
    op.create_index("ix_evidence_records_content_hash", "evidence_records", ["content_hash"])
    op.create_index("ix_evidence_records_run_kind", "evidence_records", ["run_id", "kind"])
    op.create_index(
        "ix_evidence_records_source",
        "evidence_records",
        ["source_system", "source_uri"],
    )

    op.create_table(
        "memory_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("workflow_id", sa.String(length=120), nullable=True),
        sa.Column("scope", sa.String(length=32), nullable=False),
        sa.Column("subject_id", sa.String(length=160), nullable=True),
        sa.Column("memory_key", sa.String(length=180), nullable=False),
        sa.Column("memory_value", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("embedding", pgvector.sqlalchemy.Vector(dim=1536), nullable=True),
        sa.Column("retention_class", sa.String(length=64), nullable=False),
        sa.Column("data_sensitivity", sa.String(length=64), nullable=False),
        sa.Column("source_evidence_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["workflow_runs.id"],
            name=op.f("fk_memory_records_run_id_workflow_runs"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["source_evidence_id"],
            ["evidence_records.id"],
            name=op.f("fk_memory_records_source_evidence_id_evidence_records"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_memory_records")),
        status_check("scope", MEMORY_SCOPES, "memory_scope"),
    )
    op.create_index(
        "ix_memory_records_embedding_hnsw",
        "memory_records",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
    op.create_index("ix_memory_records_scope_subject", "memory_records", ["scope", "subject_id"])
    op.create_index(
        "ix_memory_records_workflow_key",
        "memory_records",
        ["workflow_id", "memory_key"],
    )


def downgrade() -> None:
    op.drop_index("ix_memory_records_workflow_key", table_name="memory_records")
    op.drop_index("ix_memory_records_scope_subject", table_name="memory_records")
    op.drop_index("ix_memory_records_embedding_hnsw", table_name="memory_records")
    op.drop_table("memory_records")

    op.drop_index("ix_evidence_records_source", table_name="evidence_records")
    op.drop_index("ix_evidence_records_run_kind", table_name="evidence_records")
    op.drop_index("ix_evidence_records_content_hash", table_name="evidence_records")
    op.drop_table("evidence_records")

    op.drop_index("ix_model_calls_trace", table_name="model_calls")
    op.drop_index("ix_model_calls_run_started", table_name="model_calls")
    op.drop_index("ix_model_calls_model", table_name="model_calls")
    op.drop_table("model_calls")

    op.drop_index("ix_tool_calls_trace", table_name="tool_calls")
    op.drop_index("ix_tool_calls_run_started", table_name="tool_calls")
    op.drop_index("ix_tool_calls_policy_decision", table_name="tool_calls")
    op.drop_table("tool_calls")

    op.drop_index("ix_approvals_run_status", table_name="approvals")
    op.drop_index("ix_approvals_requested_at", table_name="approvals")
    op.drop_table("approvals")

    op.drop_index("ix_audit_events_workflow_created", table_name="audit_events")
    op.drop_index("ix_audit_events_trace", table_name="audit_events")
    op.drop_index("ix_audit_events_run_created", table_name="audit_events")
    op.drop_index("ix_audit_events_policy_decision", table_name="audit_events")
    op.drop_table("audit_events")

    op.drop_index("ix_workflow_runs_workflow_status", table_name="workflow_runs")
    op.drop_index("ix_workflow_runs_started_at", table_name="workflow_runs")
    op.drop_index("ix_workflow_runs_org_user", table_name="workflow_runs")
    op.drop_table("workflow_runs")

    op.drop_index(
        "ix_workflow_registry_snapshots_workflow_active",
        table_name="workflow_registry_snapshots",
    )
    op.drop_table("workflow_registry_snapshots")
