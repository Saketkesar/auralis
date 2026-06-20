"""Initial schema: core tables, enums, and append-only audit guard.

Creates every table in the AURALIS VISION relational schema along with the
PostgreSQL native enum types and the append-only INSERT-only guard on
``audit_log``. The migration is cross-dialect: on PostgreSQL it produces native
ENUM types, JSONB columns, UUID keys, and a plpgsql trigger that rejects any
UPDATE/DELETE on the audit log; on other dialects (SQLite, used for offline
validation and unit tests) enum columns degrade to VARCHAR + CHECK, JSONB to
JSON, and the audit guard is skipped (PostgreSQL-only DDL).

Revision ID: 0001_initial_schema
Revises:
Create Date: 2024-01-01 00:00:00.000000

Requirements: 1.4, 6.6, 19.1, 19.2, 20.1, 21.3, 21.4, 23.4, 24.2, 25.6, 26.1
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.models.enums import (
    ArtifactKind,
    CaseStatus,
    NodeType,
    ProviderCategory,
    ReportFormat,
    StageName,
    StageStatus,
)

# revision identifiers, used by Alembic.
revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ---------------------------------------------------------------------------
# Type helpers
# ---------------------------------------------------------------------------
def _enum(enum_cls, name: str) -> sa.Enum:
    """A named Enum that stores member *values* as the database enum labels.

    On PostgreSQL, ``op.create_table`` auto-creates the backing ``CREATE TYPE``
    exactly once per type and memoises it for the duration of the migration, so
    a type shared by two tables (``stage_name``) is created a single time. The
    types are explicitly dropped in :func:`downgrade` since ``op.drop_table``
    does not remove them. On non-PostgreSQL dialects the column renders as
    VARCHAR + CHECK and no separate type is involved.
    """
    return sa.Enum(
        enum_cls,
        name=name,
        values_callable=lambda obj: [m.value for m in obj],
        native_enum=True,
    )


def _jsonb() -> sa.types.TypeEngine:
    """JSONB on PostgreSQL, generic JSON elsewhere."""
    return postgresql.JSONB().with_variant(sa.JSON(), "sqlite")


# Named PostgreSQL ENUM types, dropped explicitly on downgrade (PostgreSQL only).
# On upgrade they are auto-created (once each) by ``op.create_table``.
_PG_ENUM_NAMES: list[str] = [
    "case_status",
    "stage_name",
    "stage_status",
    "artifact_kind",
    "kg_node_type",
    "report_format",
    "provider_category",
]


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    # Tables (parents before children). On PostgreSQL each native enum type is
    # auto-created exactly once when its first owning table is created.
    op.create_table(
        "roles",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.UniqueConstraint("name", name="uq_roles_name"),
    )

    op.create_table(
        "role_permissions",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("role_id", sa.Uuid(), nullable=False),
        sa.Column("permission", sa.String(length=128), nullable=False),
        sa.ForeignKeyConstraint(
            ["role_id"], ["roles.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint(
            "role_id", "permission", name="uq_role_permission"
        ),
    )
    op.create_index(
        "ix_role_permissions_role_id", "role_permissions", ["role_id"]
    )

    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role_id", sa.Uuid(), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["role_id"], ["roles.id"], ondelete="SET NULL"
        ),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_role_id", "users", ["role_id"])

    op.create_table(
        "cases",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=True),
        sa.Column(
            "status",
            _enum(CaseStatus, "case_status"),
            nullable=False,
            server_default=CaseStatus.QUEUED.value,
        ),
        sa.Column("original_object_key", sa.String(length=512), nullable=True),
        sa.Column("original_filename", sa.String(length=512), nullable=True),
        sa.Column("content_format", sa.String(length=16), nullable=True),
        sa.Column("final_confidence_score", sa.Float(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"], ["users.id"], ondelete="SET NULL"
        ),
    )
    op.create_index("ix_cases_owner_id", "cases", ["owner_id"])

    op.create_table(
        "stage_results",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("case_id", sa.Uuid(), nullable=False),
        sa.Column("stage", _enum(StageName, "stage_name"), nullable=False),
        sa.Column(
            "status",
            _enum(StageStatus, "stage_status"),
            nullable=False,
            server_default=StageStatus.PENDING.value,
        ),
        sa.Column("findings", _jsonb(), nullable=True),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["case_id"], ["cases.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint(
            "case_id", "stage", name="uq_stage_results_case_stage"
        ),
    )
    op.create_index("ix_stage_results_case_id", "stage_results", ["case_id"])

    op.create_table(
        "artifacts",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("case_id", sa.Uuid(), nullable=False),
        sa.Column("stage", _enum(StageName, "stage_name"), nullable=False),
        sa.Column("kind", _enum(ArtifactKind, "artifact_kind"), nullable=False),
        sa.Column("object_key", sa.String(length=512), nullable=False),
        sa.Column("mime_type", sa.String(length=255), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["case_id"], ["cases.id"], ondelete="CASCADE"
        ),
    )
    op.create_index("ix_artifacts_case_id", "artifacts", ["case_id"])

    op.create_table(
        "kg_nodes",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("case_id", sa.Uuid(), nullable=False),
        sa.Column(
            "node_type", _enum(NodeType, "kg_node_type"), nullable=False
        ),
        sa.Column("label", sa.String(length=512), nullable=False),
        sa.Column("props", _jsonb(), nullable=True),
        sa.ForeignKeyConstraint(
            ["case_id"], ["cases.id"], ondelete="CASCADE"
        ),
    )
    op.create_index("ix_kg_nodes_case_id", "kg_nodes", ["case_id"])

    op.create_table(
        "kg_edges",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("case_id", sa.Uuid(), nullable=False),
        sa.Column("src_node_id", sa.Uuid(), nullable=False),
        sa.Column("dst_node_id", sa.Uuid(), nullable=False),
        sa.Column("relation", sa.String(length=128), nullable=False),
        sa.Column("props", _jsonb(), nullable=True),
        sa.ForeignKeyConstraint(
            ["case_id"], ["cases.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["src_node_id"], ["kg_nodes.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["dst_node_id"], ["kg_nodes.id"], ondelete="CASCADE"
        ),
    )
    op.create_index("ix_kg_edges_case_id", "kg_edges", ["case_id"])
    op.create_index("ix_kg_edges_src_node_id", "kg_edges", ["src_node_id"])
    op.create_index("ix_kg_edges_dst_node_id", "kg_edges", ["dst_node_id"])

    op.create_table(
        "reports",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("case_id", sa.Uuid(), nullable=False),
        sa.Column(
            "format", _enum(ReportFormat, "report_format"), nullable=False
        ),
        sa.Column("object_key", sa.String(length=512), nullable=False),
        sa.Column("final_confidence_score", sa.Float(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["case_id"], ["cases.id"], ondelete="CASCADE"
        ),
    )
    op.create_index("ix_reports_case_id", "reports", ["case_id"])

    op.create_table(
        "provider_config",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column(
            "category",
            _enum(ProviderCategory, "provider_category"),
            nullable=False,
        ),
        sa.Column(
            "enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "timeout_seconds",
            sa.Float(),
            nullable=False,
            server_default=sa.text("10.0"),
        ),
        sa.Column("settings", _jsonb(), nullable=True),
        sa.UniqueConstraint("name", name="uq_provider_config_name"),
    )

    op.create_table(
        "audit_log",
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("target_type", sa.String(length=128), nullable=True),
        sa.Column("target_id", sa.String(length=255), nullable=True),
        sa.Column("detail", _jsonb(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["actor_id"], ["users.id"], ondelete="SET NULL"
        ),
    )
    op.create_index("ix_audit_log_actor_id", "audit_log", ["actor_id"])

    # Append-only guard on audit_log (Requirements 24.2, 25.6).
    #    Enforced by a BEFORE UPDATE/DELETE trigger that always raises, so the
    #    table is INSERT-only at the database level (PostgreSQL only).
    if is_postgres:
        op.execute(
            """
            CREATE OR REPLACE FUNCTION auralis_audit_log_no_mutate()
            RETURNS trigger AS $$
            BEGIN
                RAISE EXCEPTION
                    'audit_log is append-only: % is not permitted', TG_OP;
            END;
            $$ LANGUAGE plpgsql;
            """
        )
        op.execute(
            """
            CREATE TRIGGER audit_log_append_only
            BEFORE UPDATE OR DELETE ON audit_log
            FOR EACH ROW EXECUTE FUNCTION auralis_audit_log_no_mutate();
            """
        )


def downgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    # Drop the append-only guard first (PostgreSQL only).
    if is_postgres:
        op.execute("DROP TRIGGER IF EXISTS audit_log_append_only ON audit_log")
        op.execute("DROP FUNCTION IF EXISTS auralis_audit_log_no_mutate()")

    # Drop tables in reverse dependency order.
    op.drop_index("ix_audit_log_actor_id", table_name="audit_log")
    op.drop_table("audit_log")
    op.drop_table("provider_config")
    op.drop_index("ix_reports_case_id", table_name="reports")
    op.drop_table("reports")
    op.drop_index("ix_kg_edges_dst_node_id", table_name="kg_edges")
    op.drop_index("ix_kg_edges_src_node_id", table_name="kg_edges")
    op.drop_index("ix_kg_edges_case_id", table_name="kg_edges")
    op.drop_table("kg_edges")
    op.drop_index("ix_kg_nodes_case_id", table_name="kg_nodes")
    op.drop_table("kg_nodes")
    op.drop_index("ix_artifacts_case_id", table_name="artifacts")
    op.drop_table("artifacts")
    op.drop_index("ix_stage_results_case_id", table_name="stage_results")
    op.drop_table("stage_results")
    op.drop_index("ix_cases_owner_id", table_name="cases")
    op.drop_table("cases")
    op.drop_index("ix_users_role_id", table_name="users")
    op.drop_table("users")
    op.drop_index("ix_role_permissions_role_id", table_name="role_permissions")
    op.drop_table("role_permissions")
    op.drop_table("roles")

    # Drop native enum types last (PostgreSQL only).
    if is_postgres:
        for name in reversed(_PG_ENUM_NAMES):
            postgresql.ENUM(name=name).drop(bind, checkfirst=True)
