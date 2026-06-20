"""Enumerations shared across the AURALIS VISION ORM models.

These are declared once and reused by the models and the Alembic migration so
the database-level enum types stay in lockstep with the application code. Each
enum subclasses ``str`` so its members serialise naturally to JSON and render as
their lowercase string value as the database enum label (the models pass
``values_callable`` to SQLAlchemy's :class:`~sqlalchemy.Enum` so the stored
labels are the ``value`` strings rather than the member names).
"""
from __future__ import annotations

import enum


class CaseStatus(str, enum.Enum):
    """Lifecycle status of a Case (Requirements 1.4, 21.5, 26.1)."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETE = "complete"


class StageName(str, enum.Enum):
    """Canonical analysis-stage identifiers (Requirement 21.1).

    Covers the thirteen pipeline stages plus the dependent/auxiliary stages
    (map correlation, AI search agent, CTF, knowledge graph) described in the
    async pipeline topology.
    """

    METADATA = "metadata"
    GEOINT = "geoint"
    LANDMARK = "landmark"
    OCR = "ocr"
    REVERSE_SEARCH = "reverse_search"
    AI_SEARCH_AGENT = "ai_search_agent"
    MAP_CORRELATION = "map_correlation"
    OBJECT = "object"
    FACE = "face"
    TAMPERING = "tampering"
    AI_IMAGE = "ai_image"
    DEEPFAKE = "deepfake"
    STEGO = "stego"
    CTF = "ctf"
    THREAT = "threat"
    WEATHER = "weather"
    KNOWLEDGE_GRAPH = "knowledge_graph"


class StageStatus(str, enum.Enum):
    """Per-stage execution status (Requirements 21.3, 21.4, 21.5).

    ``COMPLETED``, ``FAILED`` and ``NOT_APPLICABLE`` are terminal states.
    """

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    NOT_APPLICABLE = "not_applicable"


class ArtifactKind(str, enum.Enum):
    """Kinds of derived artifact stored in object storage.

    Covers tampering heatmaps (12.3), extracted stego payloads (15.2), carved
    CTF files (16.4), channel images, thumbnails, and rendered reports.
    """

    THUMBNAIL = "thumbnail"
    HEATMAP = "heatmap"
    EXTRACTED_PAYLOAD = "extracted_payload"
    CARVED_FILE = "carved_file"
    CHANNEL_IMAGE = "channel_image"
    REPORT = "report"
    OTHER = "other"


class NodeType(str, enum.Enum):
    """Knowledge-graph node types (Requirement 19.1)."""

    IMAGE = "image"
    TEXT = "text"
    OBJECT = "object"
    BUSINESS = "business"
    WEBSITE = "website"
    SEARCH_RESULT = "search_result"
    LOCATION = "location"
    MAP_REFERENCE = "map_reference"
    SIMILAR_IMAGE = "similar_image"
    SOCIAL_PROFILE = "social_profile"


class ReportFormat(str, enum.Enum):
    """Supported report output formats (Requirement 20.3)."""

    PDF = "pdf"
    DOCX = "docx"
    JSON = "json"


class ProviderCategory(str, enum.Enum):
    """Search-provider categories (Requirements 6.1, 6.6, 6.7)."""

    GENERAL = "general"
    IMAGE = "image"
    MAP = "map"
    SOCIAL = "social"


__all__ = [
    "CaseStatus",
    "StageName",
    "StageStatus",
    "ArtifactKind",
    "NodeType",
    "ReportFormat",
    "ProviderCategory",
]
