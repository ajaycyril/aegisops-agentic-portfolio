from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import CheckConstraint
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from aegisops_api.db.base import Base
from aegisops_api.db.models import (
    APPROVAL_STATUSES,
    CALL_STATUSES,
    EVIDENCE_KINDS,
    EXECUTION_MODES,
    MEMORY_SCOPES,
    RUN_STATUSES,
    TOOL_RISK_CLASSES,
)

EXPECTED_TABLES = {
    "workflow_registry_snapshots",
    "workflow_runs",
    "audit_events",
    "approvals",
    "tool_calls",
    "model_calls",
    "memory_records",
    "evidence_records",
}


def test_governance_tables_are_registered() -> None:
    assert EXPECTED_TABLES.issubset(Base.metadata.tables)


def test_schema_compiles_for_postgres() -> None:
    dialect = postgresql.dialect()  # type: ignore[no-untyped-call]

    for table_name in EXPECTED_TABLES:
        table = Base.metadata.tables[table_name]
        ddl = str(CreateTable(table).compile(dialect=dialect))
        assert f"CREATE TABLE {table_name}" in ddl


def test_workflow_runs_have_controlled_status_and_mode_values() -> None:
    table = Base.metadata.tables["workflow_runs"]
    checks = {
        constraint.name: str(constraint.sqltext)
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    }

    assert all(value in checks["ck_workflow_runs_workflow_run_status"] for value in RUN_STATUSES)
    assert all(
        value in checks["ck_workflow_runs_workflow_run_execution_mode"]
        for value in EXECUTION_MODES
    )


def test_governance_status_constraints_cover_runtime_taxonomy() -> None:
    expected_values = {
        "ck_approvals_approval_status": APPROVAL_STATUSES,
        "ck_approvals_approval_risk_class": TOOL_RISK_CLASSES,
        "ck_tool_calls_tool_call_status": CALL_STATUSES,
        "ck_tool_calls_tool_call_risk_class": TOOL_RISK_CLASSES,
        "ck_model_calls_model_call_status": CALL_STATUSES,
        "ck_evidence_records_evidence_kind": EVIDENCE_KINDS,
        "ck_memory_records_memory_scope": MEMORY_SCOPES,
    }

    for table in Base.metadata.tables.values():
        checks = {
            constraint.name: str(constraint.sqltext)
            for constraint in table.constraints
            if isinstance(constraint, CheckConstraint)
        }
        for name, values in expected_values.items():
            if name in checks:
                assert all(value in checks[name] for value in values)


def test_memory_records_use_pgvector_embedding() -> None:
    table = Base.metadata.tables["memory_records"]

    assert str(table.c.embedding.type) == "VECTOR(1536)"
    assert any(index.name == "ix_memory_records_embedding_hnsw" for index in table.indexes)


def test_alembic_has_single_head() -> None:
    api_root = Path(__file__).resolve().parents[1]
    config = Config(str(api_root / "alembic.ini"))
    config.set_main_option("script_location", str(api_root / "alembic"))
    script = ScriptDirectory.from_config(config)

    assert script.get_heads() == ["0001_governance_data_layer"]
