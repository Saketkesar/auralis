"""Unit tests for the database session/base wiring (Task 1.3).

These verify the foundation that later tasks build on: a shared declarative
base, a lazily-created engine and session factory, and a database URL resolved
from configuration rather than hard-coded (Requirements 25.5, 26.1).
"""
from __future__ import annotations

import importlib

from sqlalchemy import text
from sqlalchemy.orm import DeclarativeBase

import app.database as database
from app.database import base as base_module
from app.database import session as session_module


def test_base_is_declarative_base():
    # Every ORM model subclasses this base; it must be a SQLAlchemy 2.0
    # DeclarativeBase carrying shared metadata for Alembic autogeneration.
    assert issubclass(database.Base, DeclarativeBase)
    assert database.Base.metadata is base_module.Base.metadata


def test_get_database_url_prefers_explicit_argument():
    assert (
        session_module.get_database_url("sqlite+pysqlite:///explicit.db")
        == "sqlite+pysqlite:///explicit.db"
    )


def test_get_database_url_reads_environment(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite+pysqlite:///from_env.db")
    assert session_module.get_database_url() == "sqlite+pysqlite:///from_env.db"


def test_get_database_url_falls_back_to_default(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert session_module.get_database_url() == session_module.DEFAULT_DATABASE_URL


def test_create_db_engine_builds_engine_for_url():
    engine = session_module.create_db_engine("sqlite+pysqlite:///:memory:")
    assert engine.url.render_as_string() == "sqlite+pysqlite:///:memory:"


def test_session_factory_produces_working_session(monkeypatch):
    # Point the lazily-created shared engine at an in-memory SQLite database so
    # the test needs no external service or driver, then confirm a session can
    # execute against it.
    monkeypatch.setenv("DATABASE_URL", "sqlite+pysqlite:///:memory:")
    # Reset cached singletons so the new URL takes effect.
    monkeypatch.setattr(session_module, "_engine", None)
    monkeypatch.setattr(session_module, "_session_factory", None)

    factory = session_module.get_sessionmaker()
    with factory() as db_session:
        assert db_session.execute(text("select 1")).scalar() == 1


def test_lazy_module_attributes_resolve(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite+pysqlite:///:memory:")
    monkeypatch.setattr(session_module, "_engine", None)
    monkeypatch.setattr(session_module, "_session_factory", None)

    # Accessing the convenience attributes triggers lazy creation via __getattr__.
    assert database.engine is session_module.get_engine()
    assert database.SessionLocal is session_module.get_sessionmaker()


def test_package_imports_without_opening_connection():
    # Re-importing the package must not require a database driver or a live
    # connection: creation is deferred until first use.
    importlib.reload(database)
    assert hasattr(database, "Base")
