"""Artifact ORM model.

Derived binary outputs (tampering heatmaps, extracted stego payloads, carved
CTF files, channel images, rendered reports) are stored in object storage and
referenced here (Requirements 12.3, 15.2, 16.4).
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.enums import ArtifactKind, StageName
from app.models.types import pg_enum


class Artifact(Base):
    """A derived artifact produced by an analysis stage."""

    __tablename__ = "artifacts"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    stage: Mapped[StageName] = mapped_column(
        pg_enum(StageName, "stage_name"), nullable=False
    )
    kind: Mapped[ArtifactKind] = mapped_column(
        pg_enum(ArtifactKind, "artifact_kind"), nullable=False
    )
    object_key: Mapped[str] = mapped_column(String(512), nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    case: Mapped["Case"] = relationship(back_populates="artifacts")  # noqa: F821


__all__ = ["Artifact"]
