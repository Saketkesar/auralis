"""StageResult ORM model.

One row per (case, stage). Records the stage status and findings so the pipeline
can isolate failures and track progress (Requirements 21.3, 21.4). The unique
``(case_id, stage)`` constraint guarantees a single result per stage per case.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.enums import StageName, StageStatus
from app.models.types import jsonb, pg_enum


class StageResult(Base):
    """The result of a single analysis stage for a Case."""

    __tablename__ = "stage_results"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    stage: Mapped[StageName] = mapped_column(
        pg_enum(StageName, "stage_name"), nullable=False
    )
    status: Mapped[StageStatus] = mapped_column(
        pg_enum(StageStatus, "stage_status"),
        nullable=False,
        default=StageStatus.PENDING,
        server_default=StageStatus.PENDING.value,
    )
    findings: Mapped[dict[str, Any] | None] = mapped_column(jsonb(), nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    case: Mapped["Case"] = relationship(back_populates="stage_results")  # noqa: F821

    __table_args__ = (
        # Exactly one result row per stage per case (design: unique (case_id, stage)).
        UniqueConstraint("case_id", "stage", name="uq_stage_results_case_stage"),
    )


__all__ = ["StageResult"]
