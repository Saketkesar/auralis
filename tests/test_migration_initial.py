"""Tests for the initial Alembic migration (Task 1.4).

Validates that the initial migration applies and reverses against SQLite (so it
runs without a live PostgreSQL) and that, when rendered for PostgreSQL offline,
it emits the native enum types and the append-only audit guard.
"""
from __future__ import annotations

import io
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

PROJECT_ROOT = Path(__file__).resolve().parents[1]

EXPECTED_TABLES = {
    "users",
    "roles",
    "role_permissions",
    "cases",
    "stage_results",
    "artifacts",
    "kg_nodes",
    "kg_edges",
    "reports",
    "provider_config",
    "audit_log",
}


def _alembic_config(database_url: str) -> Config:
    cfg = Config(str(PROJECT_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(PROJECT_ROOT / "migrations"))
    cfg.set_main_option("sqlalchemy.url", database_url)
    # env.py resolves the URL via get_database_url(); align it explicitly.
    import os

    os.environ["DATABASE_URL"] = database_url
    return cfg


def test_migration_upgrade_then_downgrade_sqlite(tmp_path):
    db_file = tmp_path / "migration.db"
    url = f"sqlite:///{db_file}"
    cfg = _alembic_config(url)

    command.upgrade(cfg, "head")
    eng = create_engine(url)
    try:
        names = set(inspect(eng).get_table_names())
        assert EXPECTED_TABLES.issubset(names)
        assert "alembic_version" in names
    finally:
        eng.dispose()

    command.downgrade(cfg, "base")
    eng = create_engine(url)
    try:
        names = set(inspect(eng).get_table_names())
        assert not (EXPECTED_TABLES & names)
    finally:
        eng.dispose()


def test_offline_postgres_sql_emits_enums_and_audit_guard():
    url = "postgresql+psycopg://u:p@localhost:5432/db"
    cfg = _alembic_config(url)

    # In offline mode env.py emits SQL to stdout; capture it.
    buf = io.StringIO()
    import contextlib

    with contextlib.redirect_stdout(buf):
        command.upgrade(cfg, "head", sql=True)
    sql = buf.getvalue()

    # Each of the seven native enum types created exactly once.
    assert sql.count("CREATE TYPE") == 7
    # Append-only guard installed on the audit log.
    assert "auralis_audit_log_no_mutate" in sql
    assert "CREATE TRIGGER audit_log_append_only" in sql
    assert "JSONB" in sql
