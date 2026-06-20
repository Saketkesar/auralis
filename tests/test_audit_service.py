"""Unit tests for the append-only Audit_Log service (Task 5.9).

These verify the two guarantees the service must provide (Requirement 25.6):

1. Each call appends **exactly one** audit entry per security-relevant action,
   recording the supplied ``actor_id``, ``action``, ``target_type``,
   ``target_id``, and ``detail``.
2. The service offers **no mutation path** — there is no update/delete/edit
   affordance on its public API.
"""
from __future__ import annotations

import inspect
import uuid

import pytest
from sqlalchemy import create_engine, inspect as sa_inspect
from sqlalchemy.orm import sessionmaker

from app.database.base import Base
from app.models.audit_log import AuditLog
from app.models.user import Role, User
from app.services.audit import AuditLogService, record_action


@pytest.fixture()
def session():
    """An isolated in-memory SQLite session with the schema created."""
    engine = create_engine("sqlite://", future=True)
    # Import models so every table is registered on Base.metadata.
    import app.models  # noqa: F401

    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, future=True, expire_on_commit=False)
    db = factory()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()


def _make_user(session) -> User:
    role = Role(id=uuid.uuid4(), name="analyst")
    user = User(
        id=uuid.uuid4(),
        email="analyst@example.com",
        password_hash="x",
        role_id=role.id,
        is_active=True,
    )
    session.add_all([role, user])
    session.commit()
    return user


def _count(session) -> int:
    return session.query(AuditLog).count()


def test_record_appends_exactly_one_entry(session):
    user = _make_user(session)
    svc = AuditLogService(session)

    assert _count(session) == 0

    entry = svc.record(
        "auth.login",
        actor_id=user.id,
        target_type="user",
        target_id=str(user.id),
        detail={"ip": "10.0.0.1"},
    )

    assert _count(session) == 1
    assert entry.id is not None
    assert entry.action == "auth.login"
    assert entry.actor_id == user.id
    assert entry.target_type == "user"
    assert entry.target_id == str(user.id)
    assert entry.detail == {"ip": "10.0.0.1"}
    assert entry.created_at is not None


def test_each_action_appends_one_more_entry(session):
    svc = AuditLogService(session)

    svc.record("ingest.rejected_malware", target_type="case", target_id="c1")
    assert _count(session) == 1

    svc.record("auth.logout")
    assert _count(session) == 2

    svc.record("provider.disabled", target_type="provider", target_id="bing")
    assert _count(session) == 3

    # Every recorded action is its own distinct row, never an overwrite.
    actions = {row.action for row in session.query(AuditLog).all()}
    assert actions == {
        "ingest.rejected_malware",
        "auth.logout",
        "provider.disabled",
    }


def test_record_allows_anonymous_actor(session):
    """A failed login has no resolved actor; actor_id stays NULL."""
    svc = AuditLogService(session)

    entry = svc.record("auth.login_failed", detail={"email": "nobody@example.com"})

    assert _count(session) == 1
    assert entry.actor_id is None


def test_actor_id_accepts_uuid_string(session):
    user = _make_user(session)
    svc = AuditLogService(session)

    entry = svc.record("case.opened", actor_id=str(user.id))

    assert entry.actor_id == user.id


def test_detail_is_copied_not_referenced(session):
    """Mutating the caller's dict after recording must not change the entry."""
    svc = AuditLogService(session)
    payload = {"reason": "eicar"}

    entry = svc.record("ingest.rejected_malware", detail=payload)
    payload["reason"] = "changed"

    assert entry.detail == {"reason": "eicar"}


def test_empty_action_is_rejected(session):
    svc = AuditLogService(session)

    with pytest.raises(ValueError):
        svc.record("   ")
    with pytest.raises(ValueError):
        svc.record("")

    assert _count(session) == 0


def test_record_action_helper_appends_one_entry(session):
    user = _make_user(session)

    entry = record_action(session, "report.generated", actor_id=user.id, target_id="c9")

    assert _count(session) == 1
    assert entry.action == "report.generated"
    assert entry.target_id == "c9"


def test_service_exposes_no_mutation_path():
    """The service must offer only an append (record) affordance.

    There is no update/delete/edit/remove/purge/set method through which a
    caller could alter or remove an existing audit entry (Requirement 25.6).
    """
    public = {
        name
        for name, _ in inspect.getmembers(AuditLogService, callable)
        if not name.startswith("_")
    }

    # The only public operation is the append.
    assert public == {"record"}

    forbidden_prefixes = ("update", "delete", "remove", "edit", "set", "purge", "modify")
    for name in public:
        assert not name.startswith(forbidden_prefixes), name


def test_record_is_insert_only_and_preserves_prior_entries(session):
    """Recording again never updates the prior row; both rows persist intact."""
    svc = AuditLogService(session)

    first = svc.record("auth.login", target_id="u1")
    first_id = first.id

    svc.record("auth.login", target_id="u2")

    rows = session.query(AuditLog).order_by(AuditLog.id).all()
    assert len(rows) == 2
    # The original row is untouched (same id, same target).
    assert rows[0].id == first_id
    assert rows[0].target_id == "u1"
    assert rows[1].target_id == "u2"


def test_audit_log_table_has_no_natural_update_columns(session):
    """Sanity check: the model carries no 'updated_at' — entries are immutable."""
    columns = {c.name for c in sa_inspect(AuditLog).columns}
    assert "updated_at" not in columns
    assert {"id", "actor_id", "action", "target_type", "target_id", "detail", "created_at"} <= columns
