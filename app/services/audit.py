"""Append-only Audit_Log service (Requirements 24.2, 25.6).

This service is the single application-level entry point for recording a
security-relevant action in the append-only :class:`~app.models.audit_log.AuditLog`
table. It is intentionally minimal and *append-only by construction*:

- The only persistence operation it performs is an ``INSERT`` — each call to
  :meth:`AuditLogService.record` appends **exactly one** new audit entry.
- It exposes **no** update, delete, mutate, or purge affordance. There is no
  method that modifies or removes an existing entry, by design.

Append-only behaviour is therefore enforced at two layers:

1. The database installs an INSERT-only trigger guard that raises on any
   ``UPDATE``/``DELETE`` against ``audit_log`` (see the initial migration).
2. This service offers no API surface through which a caller could attempt a
   mutation in the first place.

Keeping the surface this small makes the security-critical invariant — "audit
entries are written once and never changed" — easy to review and impossible to
violate through ordinary use of the service.
"""
from __future__ import annotations

import uuid
from typing import Any, Mapping, Optional

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog

__all__ = ["AuditLogService", "record_action"]


class AuditLogService:
    """Writes append-only audit entries for security-relevant actions.

    The service wraps a SQLAlchemy :class:`~sqlalchemy.orm.Session` and performs
    only ``INSERT`` operations. It deliberately exposes a single public
    operation, :meth:`record`; there is no update or delete path.
    """

    def __init__(self, session: Session) -> None:
        """Bind the service to a SQLAlchemy session.

        Args:
            session: The session used to persist audit entries. The caller owns
                the session's lifecycle; the service never closes it.
        """
        self._session = session

    def record(
        self,
        action: str,
        *,
        actor_id: Optional[uuid.UUID | str] = None,
        target_type: Optional[str] = None,
        target_id: Optional[str] = None,
        detail: Optional[Mapping[str, Any]] = None,
        commit: bool = True,
    ) -> AuditLog:
        """Append exactly one audit entry for a security-relevant action.

        Each invocation creates a single new :class:`AuditLog` row and inserts
        it. This method never updates or deletes an existing entry.

        Args:
            action: Short, stable identifier of the action performed (e.g.
                ``"auth.login"``, ``"ingest.rejected_malware"``). Required and
                non-empty.
            actor_id: The acting user's id, or ``None`` for system/anonymous
                actions (the column is nullable, e.g. a failed login).
            target_type: Optional type of the entity acted upon (e.g.
                ``"case"``, ``"provider"``).
            target_id: Optional identifier of the entity acted upon.
            detail: Optional JSON-serialisable mapping of extra context. It is
                copied into a plain ``dict`` so later mutation of the caller's
                object cannot alter the recorded entry.
            commit: When ``True`` (default) the entry is committed so the audit
                trail is durable independent of the surrounding unit of work.
                Pass ``False`` to enlist the insert in an outer transaction.

        Returns:
            The persisted :class:`AuditLog` entry (with its generated id
            populated).

        Raises:
            ValueError: If ``action`` is empty or not a string.
        """
        if not isinstance(action, str) or not action.strip():
            raise ValueError("audit action must be a non-empty string")

        entry = AuditLog(
            actor_id=self._coerce_actor_id(actor_id),
            action=action,
            target_type=target_type,
            target_id=None if target_id is None else str(target_id),
            detail=dict(detail) if detail is not None else None,
        )

        self._session.add(entry)
        # Flush so the generated identity is available on the returned entry
        # even when the caller defers the commit to an enclosing transaction.
        self._session.flush()
        if commit:
            self._session.commit()
        return entry

    @staticmethod
    def _coerce_actor_id(
        actor_id: Optional[uuid.UUID | str],
    ) -> Optional[uuid.UUID]:
        """Normalise an actor id to ``UUID`` (or ``None``).

        Accepts an existing :class:`uuid.UUID`, a UUID string, or ``None`` for
        system/anonymous actions.
        """
        if actor_id is None or isinstance(actor_id, uuid.UUID):
            return actor_id
        return uuid.UUID(str(actor_id))


def record_action(
    session: Session,
    action: str,
    *,
    actor_id: Optional[uuid.UUID | str] = None,
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    detail: Optional[Mapping[str, Any]] = None,
    commit: bool = True,
) -> AuditLog:
    """Convenience wrapper appending one audit entry via :class:`AuditLogService`.

    Equivalent to ``AuditLogService(session).record(...)``. Provided so callers
    that already hold a session can record an action in a single call.
    """
    return AuditLogService(session).record(
        action,
        actor_id=actor_id,
        target_type=target_type,
        target_id=target_id,
        detail=detail,
        commit=commit,
    )
