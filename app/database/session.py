"""Database engine and session factory.

This module owns the SQLAlchemy :class:`~sqlalchemy.engine.Engine` and the
``SessionLocal`` factory used by the web tier and the Celery workers. The
database URL is resolved from configuration so it is never hard-coded in source
(Requirement 25.5) and a single source of truth feeds both the runtime session
and the Alembic environment (Requirement 26.1).

Resolution order for the database URL:

1. An explicit ``url`` argument (used by tests and the Alembic env).
2. The Flask application config key ``SQLALCHEMY_DATABASE_URI`` when an
   application context is active.
3. The ``DATABASE_URL`` environment variable. The configuration module
   (``app/config.py``, built in parallel) reads the same variable, so the
   runtime and migrations stay aligned regardless of which loads first.
4. A local PostgreSQL default, so the package imports cleanly in development
   and test environments without external configuration.

The engine and ``SessionLocal`` are created lazily on first use. This keeps
importing the package cheap and free of a hard dependency on a database driver
being installed, which matters for unit tests and tooling that never open a
connection.
"""
from __future__ import annotations

import os
from typing import Optional

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

# Name of the environment variable carrying the database URL. The parallel
# configuration module references the same variable name.
DATABASE_URL_ENV_VAR = "DATABASE_URL"

# Development/test fallback. Production deployments always supply DATABASE_URL
# (or the Flask config key) so this default is never used in a real stack.
DEFAULT_DATABASE_URL = "postgresql+psycopg2://auralis:auralis@localhost:5432/auralis"

# Lazily-initialized singletons. Created on first access via get_engine() /
# get_sessionmaker() so importing this module never opens a connection or
# requires a database driver to be installed.
_engine: Optional[Engine] = None
_session_factory: Optional[sessionmaker[Session]] = None


def get_database_url(url: str | None = None) -> str:
    """Resolve the database URL from configuration.

    See the module docstring for the resolution order. The function is safe to
    call without a Flask application context.
    """
    if url:
        return url

    # Prefer the active Flask application's configuration when available.
    try:
        from flask import current_app, has_app_context

        if has_app_context():
            configured = current_app.config.get("SQLALCHEMY_DATABASE_URI") or (
                current_app.config.get(DATABASE_URL_ENV_VAR)
            )
            if configured:
                return configured
    except Exception:  # pragma: no cover - Flask always importable here
        # Never let configuration discovery break engine creation; fall through
        # to the environment-variable and default resolution below.
        pass

    return os.environ.get(DATABASE_URL_ENV_VAR, DEFAULT_DATABASE_URL)


def create_db_engine(url: str | None = None, **engine_kwargs) -> Engine:
    """Create a SQLAlchemy engine bound to the resolved database URL.

    ``pool_pre_ping`` is enabled by default so stale pooled connections (common
    behind connection-dropping proxies) are transparently recycled. This always
    creates a fresh engine; use :func:`get_engine` for the shared singleton.

    For SQLite, ``check_same_thread=False`` and a busy timeout are set so the
    background pipeline thread can share the engine with the web request thread
    (the default SQLite driver otherwise forbids cross-thread connection use).
    """
    engine_kwargs.setdefault("pool_pre_ping", True)
    engine_kwargs.setdefault("future", True)
    resolved = get_database_url(url)
    if resolved.startswith("sqlite"):
        connect_args = engine_kwargs.setdefault("connect_args", {})
        connect_args.setdefault("check_same_thread", False)
        connect_args.setdefault("timeout", 30)
    return create_engine(resolved, **engine_kwargs)


def get_engine() -> Engine:
    """Return the shared engine, creating it on first call."""
    global _engine
    if _engine is None:
        _engine = create_db_engine()
    return _engine


def get_sessionmaker() -> sessionmaker[Session]:
    """Return the shared session factory bound to the shared engine."""
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(
            bind=get_engine(),
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
            future=True,
        )
    return _session_factory


def __getattr__(name: str):
    """Lazily expose ``engine`` and ``SessionLocal`` as module attributes.

    Using PEP 562 module ``__getattr__`` lets callers ``from app.database import
    engine, SessionLocal`` while deferring actual creation until first access.
    """
    if name == "engine":
        return get_engine()
    if name == "SessionLocal":
        return get_sessionmaker()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "DATABASE_URL_ENV_VAR",
    "DEFAULT_DATABASE_URL",
    "engine",
    "SessionLocal",
    "get_engine",
    "get_sessionmaker",
    "get_database_url",
    "create_db_engine",
]
