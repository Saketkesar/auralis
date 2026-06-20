"""User, Role, and RolePermission ORM models.

Implements the identity and RBAC schema (Requirement 23.4): users belong to a
role, and a role grants a set of permissions through ``role_permissions``.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class Role(Base):
    """A named role mapping to a set of permissions (Requirement 23.4)."""

    __tablename__ = "roles"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)

    permissions: Mapped[list["RolePermission"]] = relationship(
        back_populates="role",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    users: Mapped[list["User"]] = relationship(back_populates="role")


class RolePermission(Base):
    """A single permission granted to a role (Requirement 23.4)."""

    __tablename__ = "role_permissions"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("roles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    permission: Mapped[str] = mapped_column(String(128), nullable=False)

    role: Mapped["Role"] = relationship(back_populates="permissions")

    __table_args__ = (
        # A role grants any given permission at most once.
        UniqueConstraint("role_id", "permission", name="uq_role_permission"),
    )


class User(Base):
    """An authenticated Analyst (Requirements 23.1, 23.4)."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("roles.id", ondelete="SET NULL"), nullable=True, index=True
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    role: Mapped["Role | None"] = relationship(back_populates="users")
    cases: Mapped[list["Case"]] = relationship(back_populates="owner")  # noqa: F821


__all__ = ["Role", "RolePermission", "User"]
