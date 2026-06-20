"""Database package: declarative base, engine, and session factory.

Importing from this package gives access to the shared :class:`Base` used by
all ORM models and the session factory / engine used by the web tier and Celery
workers. The Alembic environment also imports :class:`Base` (via
``Base.metadata``) and :func:`get_database_url` so migrations and runtime share
one schema definition and one configured database URL (Requirement 26.1).

``engine`` and ``SessionLocal`` are resolved lazily (see
:func:`app.database.session.get_engine` / ``get_sessionmaker``) so importing
this package never opens a database connection.
"""
from __future__ import annotations

from app.database.base import Base
from app.database.session import (
    DATABASE_URL_ENV_VAR,
    DEFAULT_DATABASE_URL,
    create_db_engine,
    get_database_url,
    get_engine,
    get_sessionmaker,
)

__all__ = [
    "Base",
    "SessionLocal",
    "engine",
    "create_db_engine",
    "get_database_url",
    "get_engine",
    "get_sessionmaker",
    "DATABASE_URL_ENV_VAR",
    "DEFAULT_DATABASE_URL",
]


def __getattr__(name: str):
    """Lazily proxy ``engine`` and ``SessionLocal`` to the session module."""
    if name == "engine":
        return get_engine()
    if name == "SessionLocal":
        return get_sessionmaker()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
