"""Case ORM model.

A Case is the persistent investigation record created on image ingestion
(Requirement 1.4) and the system of record for the pipeline (Requirements
21.5, 26.1).
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.enums import CaseStatus
from app.models.types import pg_enum


class Case(Base):
    """An investigation case anchored to a single ingested image."""

    __tablename__ = "cases"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    status: Mapped[CaseStatus] = mapped_column(
        pg_enum(CaseStatus, "case_status"),
        nullable=False,
        default=CaseStatus.QUEUED,
        server_default=CaseStatus.QUEUED.value,
    )
    # Object-storage key for the original, unmodified bytes (Requirements 1.5, 24.4).
    original_object_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    original_filename: Mapped[str | None] = mapped_column(String(512), nullable=True)
    content_format: Mapped[str | None] = mapped_column(String(16), nullable=True)
    final_confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    owner: Mapped["User | None"] = relationship(back_populates="cases")  # noqa: F821
    stage_results: Mapped[list["StageResult"]] = relationship(  # noqa: F821
        back_populates="case",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    artifacts: Mapped[list["Artifact"]] = relationship(  # noqa: F821
        back_populates="case",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    kg_nodes: Mapped[list["KGNode"]] = relationship(  # noqa: F821
        back_populates="case",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    kg_edges: Mapped[list["KGEdge"]] = relationship(  # noqa: F821
        back_populates="case",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    reports: Mapped[list["Report"]] = relationship(  # noqa: F821
        back_populates="case",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


__all__ = ["Case"]
