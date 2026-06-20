"""ORM models package.

Every model is imported here so that simply importing :mod:`app.models`
registers all tables on the shared ``Base.metadata``. The Alembic environment
(``migrations/env.py``) imports this package for autogeneration, and the
application/session layer relies on the same registry.

Models:

- :class:`~app.models.user.User`, :class:`~app.models.user.Role`,
  :class:`~app.models.user.RolePermission` — identity and RBAC (Req 23.4).
- :class:`~app.models.case.Case` — the investigation record (Req 1.4, 21.5, 26.1).
- :class:`~app.models.stage_result.StageResult` — per-stage results, unique
  ``(case_id, stage)`` (Req 21.3, 21.4).
- :class:`~app.models.artifact.Artifact` — derived object-storage outputs
  (Req 12.3, 15.2, 16.4).
- :class:`~app.models.knowledge_graph.KGNode`,
  :class:`~app.models.knowledge_graph.KGEdge` — knowledge graph (Req 19.1, 19.2).
- :class:`~app.models.report.Report` — generated reports (Req 20.1).
- :class:`~app.models.provider_config.ProviderConfig` — provider state (Req 6.6).
- :class:`~app.models.audit_log.AuditLog` — append-only audit log (Req 24.2, 25.6).
"""
from __future__ import annotations

from app.database.base import Base
from app.models.artifact import Artifact
from app.models.audit_log import AuditLog
from app.models.case import Case
from app.models.enums import (
    ArtifactKind,
    CaseStatus,
    NodeType,
    ProviderCategory,
    ReportFormat,
    StageName,
    StageStatus,
)
from app.models.knowledge_graph import KGEdge, KGNode
from app.models.provider_config import ProviderConfig
from app.models.report import Report
from app.models.stage_result import StageResult
from app.models.user import Role, RolePermission, User

__all__ = [
    "Base",
    # Models
    "User",
    "Role",
    "RolePermission",
    "Case",
    "StageResult",
    "Artifact",
    "KGNode",
    "KGEdge",
    "Report",
    "ProviderConfig",
    "AuditLog",
    # Enums
    "CaseStatus",
    "StageName",
    "StageStatus",
    "ArtifactKind",
    "NodeType",
    "ReportFormat",
    "ProviderCategory",
]
