"""ProviderConfig ORM model.

Persisted enable/disable state and settings for pluggable search providers, read
on each Search_Hub dispatch (Requirements 6.6, 6.7).
"""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import Boolean, Float, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.models.enums import ProviderCategory
from app.models.types import jsonb, pg_enum


class ProviderConfig(Base):
    """Configuration for a registered search provider."""

    __tablename__ = "provider_config"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    category: Mapped[ProviderCategory] = mapped_column(
        pg_enum(ProviderCategory, "provider_category"), nullable=False
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    timeout_seconds: Mapped[float] = mapped_column(
        Float, nullable=False, default=10.0, server_default="10.0"
    )
    settings: Mapped[dict[str, Any] | None] = mapped_column(jsonb(), nullable=True)


__all__ = ["ProviderConfig"]
