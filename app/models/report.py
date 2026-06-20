"""Report ORM model.

A rendered investigation report (PDF/DOCX/JSON) stored in object storage with
its final Confidence_Score (Requirement 20).
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.enums import ReportFormat
from app.models.types import pg_enum


class Report(Base):
    """A generated report for a Case."""

    __tablename__ = "reports"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    format: Mapped[ReportFormat] = mapped_column(
        pg_enum(ReportFormat, "report_format"), nullable=False
    )
    object_key: Mapped[str] = mapped_column(String(512), nullable=False)
    final_confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    case: Mapped["Case"] = relationship(back_populates="reports")  # noqa: F821


__all__ = ["Report"]
