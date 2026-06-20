"""RBAC authorization (Requirements 23.4, 23.5).

This module implements the ``Authorization_Service`` from the design's Security
Architecture as a permission-based access-control layer. Roles map to a set of
permissions (``Role`` → ``RolePermission`` in :mod:`app.models.user`), and an
action is permitted only when the authenticated Analyst's role grants the
required permission.

The public surface is the :func:`require_permission` decorator described in the
design ("permission-based checks via a ``@require_permission(perm)`` decorator
on routes/services"). When applied to a view or service function it:

* resolves the authenticated principal (by default from Flask's request-scoped
  ``g``, where the authentication layer of Task 5.1/5.10 deposits the verified
  user), then
* looks up the permission set granted to that principal's role, and
* permits the wrapped call only when the required permission is present
  (Requirement 23.4); otherwise it denies the action by raising
  :class:`AuthorizationError` — an HTTP ``403`` carrying an authorization
  failure *message* (Requirement 23.5).

Like :mod:`app.security.auth`, the core logic is decoupled from Flask: the
permission resolution helpers (:func:`permissions_for`, :func:`has_permission`)
are pure functions over a principal object, and the decorator accepts a custom
``loader`` so it can be unit-tested without a request context.
"""
from __future__ import annotations

import functools
from typing import Any, Callable, Iterable, TypeVar

# A single, non-specific message returned/raised when a role lacks the required
# permission (Requirement 23.5). It deliberately avoids naming the permission so
# the response does not enumerate the platform's permission scheme to clients.
AUTHORIZATION_FAILURE_MESSAGE = "You do not have permission to perform this action."

F = TypeVar("F", bound=Callable[..., Any])


class AuthorizationError(Exception):
    """Raised when a principal's role does not grant the required permission.

    Carries an HTTP ``403`` status and an authorization failure message so a
    Flask error handler (or a caller) can render a uniform denial response
    (Requirement 23.5). The offending permission is recorded on
    :attr:`required_permission` for audit/logging without being leaked in the
    user-facing message.
    """

    status_code = 403

    def __init__(
        self,
        message: str = AUTHORIZATION_FAILURE_MESSAGE,
        *,
        required_permission: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.required_permission = required_permission


# ---------------------------------------------------------------------------
# Permission resolution
# ---------------------------------------------------------------------------
def _normalize_permissions(value: Iterable[Any]) -> frozenset[str]:
    """Coerce a permissions collection into a set of permission strings.

    Accepts either plain permission strings or ``RolePermission``-like objects
    exposing a ``.permission`` attribute, so the resolver works against ORM rows
    and lightweight test doubles alike.
    """
    result: set[str] = set()
    for item in value:
        if isinstance(item, str):
            result.add(item)
            continue
        permission = getattr(item, "permission", None)
        if isinstance(permission, str):
            result.add(permission)
    return frozenset(result)


def permissions_for(principal: Any) -> frozenset[str]:
    """Return the set of permissions granted to ``principal``.

    Resolution mirrors the data model (Requirement 23.4): a ``User`` carries a
    ``role`` whose ``permissions`` enumerate the granted permission strings. The
    helper also tolerates being handed a ``Role`` directly, or a bare iterable of
    permission strings/objects, which keeps both routes and unit tests simple.

    A principal of ``None`` — for example, an unauthenticated request — yields no
    permissions, so every permission check against it denies.
    """
    if principal is None:
        return frozenset()

    # Prefer the principal's role; fall back to treating the principal itself as
    # the permission holder (e.g. when a Role is passed directly).
    role = getattr(principal, "role", None)
    holder = role if role is not None else principal

    perms = getattr(holder, "permissions", None)
    if perms is not None:
        return _normalize_permissions(perms)

    # A bare iterable of permission strings/objects (but not a string itself).
    if not isinstance(principal, (str, bytes)) and isinstance(principal, Iterable):
        return _normalize_permissions(principal)

    return frozenset()


def has_permission(principal: Any, permission: str) -> bool:
    """Return ``True`` iff ``principal``'s role grants ``permission``.

    This is the pure decision function behind :func:`require_permission`
    (Requirement 23.4): an action is permitted exactly when the required
    permission is a member of the principal's resolved permission set.
    """
    return permission in permissions_for(principal)


# ---------------------------------------------------------------------------
# Principal resolution from the request context
# ---------------------------------------------------------------------------
def _default_principal_loader() -> Any:
    """Resolve the authenticated principal from Flask's request-scoped ``g``.

    The authentication layer (Task 5.1/5.10) verifies the presented JWT/session
    token and stores the resulting user on ``g``. This loader looks for the user
    under a few conventional attribute names and returns ``None`` when no
    authenticated principal is present (which causes the decorator to deny).
    """
    try:  # pragma: no cover - import guard for non-Flask contexts
        from flask import g
    except ImportError:  # pragma: no cover
        return None

    for attr in ("current_user", "current_principal", "user"):
        principal = getattr(g, attr, None)
        if principal is not None:
            return principal
    return None


# ---------------------------------------------------------------------------
# The decorator
# ---------------------------------------------------------------------------
def require_permission(
    permission: str,
    *,
    loader: Callable[[], Any] | None = None,
) -> Callable[[F], F]:
    """Permit the wrapped action only when the role grants ``permission``.

    Applied as ``@require_permission("cases:create")`` to a view or service
    function, the returned decorator resolves the authenticated principal (via
    ``loader`` or, by default, Flask's ``g``), looks up the permissions granted
    to its role, and:

    * calls the wrapped function when the permission is granted (Requirement
      23.4); or
    * denies by raising :class:`AuthorizationError` (HTTP ``403``) with an
      authorization failure message when it is not (Requirement 23.5).

    ``loader`` is injectable so the decorator can be exercised without a Flask
    request context.
    """
    resolve = loader or _default_principal_loader

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            principal = resolve()
            if not has_permission(principal, permission):
                raise AuthorizationError(
                    AUTHORIZATION_FAILURE_MESSAGE,
                    required_permission=permission,
                )
            return func(*args, **kwargs)

        # Expose the guarded permission for introspection/auditing.
        wrapper.required_permission = permission  # type: ignore[attr-defined]
        return wrapper  # type: ignore[return-value]

    return decorator


__all__ = [
    "AUTHORIZATION_FAILURE_MESSAGE",
    "AuthorizationError",
    "require_permission",
    "has_permission",
    "permissions_for",
]
