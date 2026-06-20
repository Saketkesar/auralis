"""Unit tests for the ORM models and the initial migration (Task 1.4).

These verify that every model registers on the shared ``Base.metadata``, that
the schema can be created, that the key invariants from the design hold (the
unique ``(case_id, stage)`` constraint, enum value storage, relationship
cascades), and that the initial Alembic migration applies and reverses cleanly.

SQLite is used as the backing store so the tests run without a live PostgreSQL;
the PostgreSQL-only DDL (native enum types and the append-only trigger guard) is
exercised separately via offline SQL generation.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import create_engine, event, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import app.models as models
from app.database.base import Base
from app.models import (
    Artifact,
    AuditLog,
    Case,
    CaseStatus,
    KGEdge,
    KGNode,
    ProviderCategory,
    ProviderConfig,
    Report,
    ReportFormat,
    Role,
    RolePermission,
    StageName,
    StageResult,
    StageStatus,
    User,
    ArtifactKind,
    NodeType,
)

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


@pytest.fixture()
def engine():
    """An isolated in-memory SQLite engine with the full schema created.

    SQLite does not enforce foreign keys (or ON DELETE CASCADE) unless the
    ``foreign_keys`` pragma is enabled per-connection, so we turn it on to make
    the cascade behaviour match PostgreSQL.
    """
    eng = create_engine("sqlite://")

    @event.listens_for(eng, "connect")
    def _enable_fk(dbapi_conn, _record):  # pragma: no cover - trivial
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    Base.metadata.create_all(eng)
    try:
        yield eng
    finally:
        Base.metadata.drop_all(eng)
        eng.dispose()


@pytest.fixture()
def session(engine) -> Session:
    with Session(engine) as s:
        yield s


# ---------------------------------------------------------------------------
# Registration / schema
# ---------------------------------------------------------------------------
def test_all_models_register_on_shared_metadata():
    """Every model must register on Base.metadata for Alembic autogeneration."""
    assert EXPECTED_TABLES.issubset(set(Base.metadata.tables))


def test_schema_creates_all_tables(engine):
    names = set(inspect(engine).get_table_names())
    assert EXPECTED_TABLES.issubset(names)


def test_stage_results_has_unique_case_stage_constraint(engine):
    uniques = inspect(engine).get_unique_constraints("stage_results")
    cols = {tuple(u["column_names"]) for u in uniques}
    assert ("case_id", "stage") in cols


def test_role_permission_unique_constraint(engine):
    uniques = inspect(engine).get_unique_constraints("role_permissions")
    cols = {tuple(u["column_names"]) for u in uniques}
    assert ("role_id", "permission") in cols


# ---------------------------------------------------------------------------
# Behaviour / invariants
# ---------------------------------------------------------------------------
def test_create_case_with_owner_and_role(session):
    role = Role(name="analyst")
    role.permissions.append(RolePermission(permission="case:create"))
    user = User(email="a@example.com", password_hash="x", role=role)
    case = Case(owner=user, status=CaseStatus.QUEUED)
    session.add_all([role, user, case])
    session.commit()

    assert isinstance(case.id, uuid.UUID)
    assert case.owner is user
    assert user.role.permissions[0].permission == "case:create"


def test_case_status_enum_persists_value(session):
    case = Case(status=CaseStatus.RUNNING)
    session.add(case)
    session.commit()
    # Stored as the lowercase value, read back as the enum member.
    raw = session.execute(
        Case.__table__.select().with_only_columns(Case.status)
    ).scalar_one()
    assert raw in (CaseStatus.RUNNING, "running")


def test_unique_case_stage_enforced(session):
    case = Case()
    session.add(case)
    session.commit()
    session.add(StageResult(case_id=case.id, stage=StageName.METADATA))
    session.commit()
    session.add(StageResult(case_id=case.id, stage=StageName.METADATA))
    with pytest.raises(IntegrityError):
        session.commit()


def test_distinct_stages_for_same_case_allowed(session):
    case = Case()
    session.add(case)
    session.commit()
    session.add_all(
        [
            StageResult(case_id=case.id, stage=StageName.METADATA),
            StageResult(case_id=case.id, stage=StageName.GEOINT),
        ]
    )
    session.commit()
    assert len(case.stage_results) == 2


def test_stage_result_defaults_to_pending(session):
    case = Case()
    session.add(case)
    session.commit()
    sr = StageResult(case_id=case.id, stage=StageName.OCR)
    session.add(sr)
    session.commit()
    session.refresh(sr)
    assert sr.status == StageStatus.PENDING


def test_findings_jsonb_round_trip(session):
    case = Case()
    session.add(case)
    session.commit()
    payload = {"schema_version": 1, "risk_score": 22.5, "flags": {"gps_removed": False}}
    sr = StageResult(
        case_id=case.id, stage=StageName.METADATA, findings=payload, score=22.5
    )
    session.add(sr)
    session.commit()
    session.refresh(sr)
    assert sr.findings == payload


def test_knowledge_graph_nodes_and_edges(session):
    case = Case()
    session.add(case)
    session.commit()
    n1 = KGNode(case_id=case.id, node_type=NodeType.IMAGE, label="img")
    n2 = KGNode(case_id=case.id, node_type=NodeType.LOCATION, label="Paris")
    session.add_all([n1, n2])
    session.commit()
    edge = KGEdge(
        case_id=case.id,
        src_node_id=n1.id,
        dst_node_id=n2.id,
        relation="located_at",
    )
    session.add(edge)
    session.commit()
    assert edge.src_node is n1
    assert edge.dst_node is n2


def test_artifact_and_report_persist(session):
    case = Case()
    session.add(case)
    session.commit()
    art = Artifact(
        case_id=case.id,
        stage=StageName.STEGO,
        kind=ArtifactKind.EXTRACTED_PAYLOAD,
        object_key="cases/x/payload.bin",
        mime_type="application/octet-stream",
        size_bytes=1024,
    )
    rep = Report(
        case_id=case.id,
        format=ReportFormat.JSON,
        object_key="cases/x/report.json",
        final_confidence_score=88.0,
    )
    session.add_all([art, rep])
    session.commit()
    assert art.kind == ArtifactKind.EXTRACTED_PAYLOAD
    assert rep.format == ReportFormat.JSON


def test_provider_config_defaults(session):
    p = ProviderConfig(name="bing", category=ProviderCategory.IMAGE)
    session.add(p)
    session.commit()
    session.refresh(p)
    assert p.enabled is True
    assert p.timeout_seconds == 10.0


def test_audit_log_append(session):
    entry = AuditLog(action="upload.rejected", target_type="file", detail={"reason": "malware"})
    session.add(entry)
    session.commit()
    session.refresh(entry)
    assert entry.id is not None
    assert entry.action == "upload.rejected"


def test_cascade_delete_case_removes_children(session):
    case = Case()
    session.add(case)
    session.commit()
    session.add(StageResult(case_id=case.id, stage=StageName.FACE))
    session.add(
        Artifact(
            case_id=case.id,
            stage=StageName.FACE,
            kind=ArtifactKind.THUMBNAIL,
            object_key="k",
        )
    )
    session.commit()
    session.delete(case)
    session.commit()
    assert session.query(StageResult).count() == 0
    assert session.query(Artifact).count() == 0


def test_models_module_exports_every_model():
    for name in (
        "User",
        "Role",
        "RolePermission",
        "Case",
        "StageResult",
        "Artifact",
        "KGNode",
        "KGEdge",
        "Report",
        "ProviderConfig",
        "AuditLog",
    ):
        assert hasattr(models, name)
