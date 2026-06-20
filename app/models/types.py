"""Reusable column-type helpers for the ORM models.

The design targets PostgreSQL (JSONB findings, native enums, UUID keys) but the
models stay dialect-portable so the schema can also be created on SQLite for
offline migration validation and unit tests. The helpers here centralise the
cross-dialect type choices.
"""
from __future__ import annotations

import enum
from typing import Any

from sqlalchemy import Enum as SAEnum
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import TypeEngine


def jsonb() -> TypeEngine[Any]:
    """Return a JSONB column type that degrades to generic JSON off PostgreSQL.

    On PostgreSQL the column is ``JSONB`` (as the design specifies); on other
    dialects (e.g. SQLite used in tests/offline validation) it renders as the
    generic ``JSON`` type so the same models work everywhere.
    """
    return JSONB().with_variant(JSON(), "sqlite")


def pg_enum(enum_cls: type[enum.Enum], name: str) -> SAEnum:
    """Build a named SQLAlchemy ``Enum`` that stores the member *values*.

    Using ``values_callable`` makes the database enum labels the lowercase
    string ``value`` of each member (e.g. ``"queued"``) rather than the Python
    member name (``"QUEUED"``). The explicit ``name`` is required so PostgreSQL
    creates a stable, reusable native enum type.
    """
    return SAEnum(
        enum_cls,
        name=name,
        values_callable=lambda obj: [member.value for member in obj],
        native_enum=True,
    )


__all__ = ["jsonb", "pg_enum"]
