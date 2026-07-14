from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column

from aegisops_api.db.base import Base

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


def utc_now() -> datetime:
    return datetime.now(UTC)


def status_check(column_name: str, allowed_values: tuple[str, ...], name: str) -> CheckConstraint:
    quoted_values = ", ".join(f"'{value}'" for value in allowed_values)
    return CheckConstraint(f"{column_name} in ({quoted_values})", name=name)


class WorkflowRegistrySnapshot(Base):
    __tablename__ = "workflow_registry_snapshots"
    __table_args__ = (
        UniqueConstraint("workflow_id", "version", name="uq_workflow_registry_snapshot_version"),
        Index("ix_workflow_registry_snapshots_workflow_active", "workflow_id", "is_active"),
    )

    id: Mapped[UUID] = mapped_column(postgresql.UUID(as_uuid=True), primary_key=True, default=uuid4)
    workflow_id: Mapped[str] = mapped_column(String(120), nullable=False)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    source_path: Mapped[str | None] = mapped_column(String(512))
    config_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    config: Mapped[dict[str, Any]] = mapped_column(postgresql.JSONB, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )


class WorkflowRun(Base):
    __tablename__ = "workflow_runs"
    __table_args__ = (
        status_check("status", RUN_STATUSES, "workflow_run_status"),
        status_check("execution_mode", EXECUTION_MODES, "workflow_run_execution_mode"),
        Index("ix_workflow_runs_workflow_status", "workflow_id", "status"),
        Index("ix_workflow_runs_org_user", "org_id", "user_id"),
        Index("ix_workflow_runs_started_at", "started_at"),
    )

    id: Mapped[UUID] = mapped_column(postgresql.UUID(as_uuid=True), primary_key=True, default=uuid4)
    workflow_id: Mapped[str] = mapped_column(String(120), nullable=False)
    registry_snapshot_id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        ForeignKey("workflow_registry_snapshots.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    execution_mode: Mapped[str] = mapped_column(String(24), nullable=False, default="replay")
    autonomy_level: Mapped[str] = mapped_column(String(64), nullable=False)
    org_id: Mapped[str | None] = mapped_column(String(120))
    user_id: Mapped[str | None] = mapped_column(String(120))
    input_payload: Mapped[dict[str, Any]] = mapped_column(
        postgresql.JSONB,
        nullable=False,
        default=dict,
    )
    budget: Mapped[dict[str, Any]] = mapped_column(postgresql.JSONB, nullable=False, default=dict)
    policy_context: Mapped[dict[str, Any]] = mapped_column(
        postgresql.JSONB,
        nullable=False,
        default=dict,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_reason: Mapped[str | None] = mapped_column(Text)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_events_run_created", "run_id", "created_at"),
        Index("ix_audit_events_workflow_created", "workflow_id", "created_at"),
        Index("ix_audit_events_policy_decision", "policy_decision_id"),
        Index("ix_audit_events_trace", "trace_id"),
    )

    id: Mapped[UUID] = mapped_column(postgresql.UUID(as_uuid=True), primary_key=True, default=uuid4)
    run_id: Mapped[UUID | None] = mapped_column(
        postgresql.UUID(as_uuid=True),
        ForeignKey("workflow_runs.id", ondelete="SET NULL"),
    )
    workflow_id: Mapped[str | None] = mapped_column(String(120))
    event_type: Mapped[str] = mapped_column(String(120), nullable=False)
    actor_type: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_id: Mapped[str | None] = mapped_column(String(120))
    action: Mapped[str] = mapped_column(String(160), nullable=False)
    resource_type: Mapped[str | None] = mapped_column(String(120))
    resource_id: Mapped[str | None] = mapped_column(String(160))
    policy_decision_id: Mapped[str | None] = mapped_column(String(160))
    trace_id: Mapped[str | None] = mapped_column(String(160))
    data_sensitivity: Mapped[str] = mapped_column(String(64), nullable=False, default="internal")
    payload: Mapped[dict[str, Any]] = mapped_column(postgresql.JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )


class Approval(Base):
    __tablename__ = "approvals"
    __table_args__ = (
        status_check("status", APPROVAL_STATUSES, "approval_status"),
        status_check("risk_class", TOOL_RISK_CLASSES, "approval_risk_class"),
        Index("ix_approvals_run_status", "run_id", "status"),
        Index("ix_approvals_requested_at", "requested_at"),
    )

    id: Mapped[UUID] = mapped_column(postgresql.UUID(as_uuid=True), primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        ForeignKey("workflow_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    risk_class: Mapped[str] = mapped_column(String(32), nullable=False)
    requested_action: Mapped[str] = mapped_column(String(160), nullable=False)
    requested_by: Mapped[str] = mapped_column(String(120), nullable=False)
    approver_id: Mapped[str | None] = mapped_column(String(120))
    request_payload: Mapped[dict[str, Any]] = mapped_column(
        postgresql.JSONB,
        nullable=False,
        default=dict,
    )
    decision_payload: Mapped[dict[str, Any]] = mapped_column(
        postgresql.JSONB,
        nullable=False,
        default=dict,
    )
    policy_decision_id: Mapped[str | None] = mapped_column(String(160))
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ToolCall(Base):
    __tablename__ = "tool_calls"
    __table_args__ = (
        status_check("status", CALL_STATUSES, "tool_call_status"),
        status_check("risk_class", TOOL_RISK_CLASSES, "tool_call_risk_class"),
        Index("ix_tool_calls_run_started", "run_id", "started_at"),
        Index("ix_tool_calls_trace", "trace_id"),
        Index("ix_tool_calls_policy_decision", "policy_decision_id"),
    )

    id: Mapped[UUID] = mapped_column(postgresql.UUID(as_uuid=True), primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        ForeignKey("workflow_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    approval_id: Mapped[UUID | None] = mapped_column(
        postgresql.UUID(as_uuid=True),
        ForeignKey("approvals.id", ondelete="SET NULL"),
    )
    tool_name: Mapped[str] = mapped_column(String(160), nullable=False)
    tool_version: Mapped[str] = mapped_column(String(64), nullable=False)
    risk_class: Mapped[str] = mapped_column(String(32), nullable=False)
    input_schema_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    input_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    output_hash: Mapped[str | None] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    policy_decision_id: Mapped[str | None] = mapped_column(String(160))
    trace_id: Mapped[str | None] = mapped_column(String(160))
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    call_metadata: Mapped[dict[str, Any]] = mapped_column(
        postgresql.JSONB,
        nullable=False,
        default=dict,
    )
    error_message: Mapped[str | None] = mapped_column(Text)


class ModelCall(Base):
    __tablename__ = "model_calls"
    __table_args__ = (
        status_check("status", CALL_STATUSES, "model_call_status"),
        Index("ix_model_calls_run_started", "run_id", "started_at"),
        Index("ix_model_calls_trace", "trace_id"),
        Index("ix_model_calls_model", "provider", "model"),
    )

    id: Mapped[UUID] = mapped_column(postgresql.UUID(as_uuid=True), primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        ForeignKey("workflow_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(String(80), nullable=False)
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    purpose: Mapped[str] = mapped_column(String(120), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(120), nullable=False)
    input_token_count: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    output_token_count: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    estimated_cost_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False, default=0)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    trace_id: Mapped[str | None] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    policy_context: Mapped[dict[str, Any]] = mapped_column(
        postgresql.JSONB,
        nullable=False,
        default=dict,
    )
    request_metadata: Mapped[dict[str, Any]] = mapped_column(
        postgresql.JSONB,
        nullable=False,
        default=dict,
    )
    response_metadata: Mapped[dict[str, Any]] = mapped_column(
        postgresql.JSONB,
        nullable=False,
        default=dict,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)


class EvidenceRecord(Base):
    __tablename__ = "evidence_records"
    __table_args__ = (
        status_check("kind", EVIDENCE_KINDS, "evidence_kind"),
        Index("ix_evidence_records_run_kind", "run_id", "kind"),
        Index("ix_evidence_records_source", "source_system", "source_uri"),
        Index("ix_evidence_records_content_hash", "content_hash"),
    )

    id: Mapped[UUID] = mapped_column(postgresql.UUID(as_uuid=True), primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        ForeignKey("workflow_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    workflow_id: Mapped[str] = mapped_column(String(120), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    source_system: Mapped[str] = mapped_column(String(120), nullable=False)
    source_uri: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    evidence_metadata: Mapped[dict[str, Any]] = mapped_column(
        postgresql.JSONB,
        nullable=False,
        default=dict,
    )
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )


class MemoryRecord(Base):
    __tablename__ = "memory_records"
    __table_args__ = (
        status_check("scope", MEMORY_SCOPES, "memory_scope"),
        Index("ix_memory_records_workflow_key", "workflow_id", "memory_key"),
        Index("ix_memory_records_scope_subject", "scope", "subject_id"),
        Index(
            "ix_memory_records_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    id: Mapped[UUID] = mapped_column(postgresql.UUID(as_uuid=True), primary_key=True, default=uuid4)
    run_id: Mapped[UUID | None] = mapped_column(
        postgresql.UUID(as_uuid=True),
        ForeignKey("workflow_runs.id", ondelete="SET NULL"),
    )
    workflow_id: Mapped[str | None] = mapped_column(String(120))
    scope: Mapped[str] = mapped_column(String(32), nullable=False)
    subject_id: Mapped[str | None] = mapped_column(String(160))
    memory_key: Mapped[str] = mapped_column(String(180), nullable=False)
    memory_value: Mapped[dict[str, Any]] = mapped_column(postgresql.JSONB, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536))
    retention_class: Mapped[str] = mapped_column(String(64), nullable=False)
    data_sensitivity: Mapped[str] = mapped_column(String(64), nullable=False, default="internal")
    source_evidence_id: Mapped[UUID | None] = mapped_column(
        postgresql.UUID(as_uuid=True),
        ForeignKey("evidence_records.id", ondelete="SET NULL"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
