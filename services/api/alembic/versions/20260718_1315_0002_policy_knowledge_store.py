"""Create governed policy knowledge store.

Revision ID: 0002_policy_knowledge_store
Revises: 0001_governance_data_layer
Create Date: 2026-07-18 13:15:00.000000+00:00
"""

from collections.abc import Sequence

import pgvector.sqlalchemy
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0002_policy_knowledge_store"
down_revision: str | None = "0001_governance_data_layer"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(sa.text("CREATE EXTENSION IF NOT EXISTS vector"))

    op.create_table(
        "policy_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", sa.String(length=120), nullable=True),
        sa.Column("scenario_id", sa.String(length=120), nullable=False),
        sa.Column("authority", sa.String(length=240), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("source_uri", sa.Text(), nullable=False),
        sa.Column("version", sa.String(length=160), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("document_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_policy_documents")),
        sa.UniqueConstraint(
            "tenant_id",
            "source_uri",
            "content_hash",
            name="uq_policy_document_tenant_source_hash",
        ),
        sa.CheckConstraint(
            "status in ('active', 'superseded', 'withdrawn')",
            name="policy_document_status",
        ),
    )
    op.create_index(
        "ix_policy_documents_scenario_status",
        "policy_documents",
        ["scenario_id", "status"],
    )
    op.create_index(
        "ix_policy_documents_tenant_scenario",
        "policy_documents",
        ["tenant_id", "scenario_id"],
    )

    op.create_table(
        "policy_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("section", sa.String(length=500), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column(
            "search_vector",
            postgresql.TSVECTOR(),
            sa.Computed("to_tsvector('english', content)", persisted=True),
            nullable=False,
        ),
        sa.Column("embedding_model", sa.String(length=160), nullable=True),
        sa.Column("embedding", pgvector.sqlalchemy.Vector(1536), nullable=True),
        sa.Column("chunk_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["policy_documents.id"],
            name=op.f("fk_policy_chunks_document_id_policy_documents"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_policy_chunks")),
        sa.UniqueConstraint("document_id", "ordinal", name="uq_policy_chunk_document_ordinal"),
    )
    op.create_index(
        "ix_policy_chunks_document",
        "policy_chunks",
        ["document_id", "ordinal"],
    )
    op.execute(
        sa.text("CREATE INDEX ix_policy_chunks_fts ON policy_chunks USING gin (search_vector)")
    )
    op.execute(
        sa.text(
            "CREATE INDEX ix_policy_chunks_embedding ON policy_chunks "
            "USING hnsw (embedding vector_cosine_ops) WHERE embedding IS NOT NULL"
        )
    )


def downgrade() -> None:
    op.drop_table("policy_chunks")
    op.drop_table("policy_documents")
