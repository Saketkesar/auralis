"""AuditLog ORM model.

The append-only record of security-relevant actions (Requirements 24.2, 25.6).
Append-only behaviour is enforced at the database level by the initial
migration, which installs an INSERT-only trigger guard that raises on any
UPDATE or DELETE against this table. The ORM model itself exposes no update or
delete affordance beyond ordinary SQLAlchemy semantics; the database guard is
the authoritative enforcement.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.models.types import jsonb


class AuditLog(Base):
    """An append-only audit entry for a security-relevant action."""

    __tablename__ = "audit_log"

    # bigserial-style identity key (design: id bigserial). BigInteger on
    # PostgreSQL (BIGSERIAL/identity); degrades to autoincrementing INTEGER on
    # SQLite, which only treats ``INTEGER PRIMARY KEY`` as a rowid alias.
    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer(), "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    target_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    target_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    detail: Mapped[dict[str, Any] | None] = mapped_column(jsonb(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


__all__ = ["AuditLog"]
