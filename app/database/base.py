"""Declarative base for all AURALIS VISION ORM models.

A single :class:`Base` is shared by every model so that Alembic can discover the
full schema through ``Base.metadata`` and so the session factory binds against a
consistent registry. ORM models (Task 1.4) subclass this base.
"""
from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Common declarative base.

    Subclassing SQLAlchemy 2.0's :class:`~sqlalchemy.orm.DeclarativeBase` gives
    every model typed mapping support and a shared ``metadata`` object used by
    the Alembic environment for autogeneration.
    """


__all__ = ["Base"]
