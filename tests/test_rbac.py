"""Unit tests for RBAC authorization (Task 5.2; Requirements 23.4, 23.5).

These exercise the ``@require_permission`` decorator and its permission
resolution helpers across the two outcomes the requirement defines:

* the role grants the required permission → the action is permitted (23.4);
* the role does not grant it → the action is denied with an authorization
  failure message and an HTTP 403 status (23.5).

Lightweight role/user doubles stand in for the ORM models so the security logic
is tested in isolation, plus a Flask-context test covers the default principal
loader.
"""
from __future__ import annotations

import pytest
from flask import Flask, g

from app.security.rbac import (
    AUTHORIZATION_FAILURE_MESSAGE,
    AuthorizationError,
    has_permission,
    permissions_for,
    require_permission,
)


# ---------------------------------------------------------------------------
# Test doubles mirroring app.models.user.{Role, RolePermission, User}
# ---------------------------------------------------------------------------
class FakePermission:
    """Mirrors RolePermission: exposes a ``.permission`` string."""

    def __init__(self, permission: str) -> None:
        self.permission = permission


class FakeRole:
    """Mirrors Role: exposes a ``.permissions`` list of RolePermission-likes."""

    def __init__(self, *permissions: str) -> None:
        self.permissions = [FakePermission(p) for p in permissions]


class FakeUser:
    """Mirrors User: carries a ``.role`` (which may be None)."""

    def __init__(self, role: FakeRole | None) -> None:
        self.role = role


# ---------------------------------------------------------------------------
# permissions_for / has_permission
# ---------------------------------------------------------------------------
def test_permissions_for_resolves_role_permission_objects():
    user = FakeUser(FakeRole("cases:create", "cases:read"))
    assert permissions_for(user) == frozenset({"cases:create", "cases:read"})


def test_permissions_for_accepts_a_role_directly():
    assert permissions_for(FakeRole("reports:export")) == frozenset({"reports:export"})


def test_permissions_for_accepts_bare_string_iterable():
    assert permissions_for(["a", "b"]) == frozenset({"a", "b"})


def test_permissions_for_none_principal_is_empty():
    assert permissions_for(None) == frozenset()


def test_permissions_for_user_without_role_is_empty():
    assert permissions_for(FakeUser(None)) == frozenset()


def test_has_permission_true_when_granted():
    user = FakeUser(FakeRole("cases:create"))
    assert has_permission(user, "cases:create") is True


def test_has_permission_false_when_not_granted():
    user = FakeUser(FakeRole("cases:read"))
    assert has_permission(user, "cases:create") is False


# ---------------------------------------------------------------------------
# require_permission decorator — granted path (Requirement 23.4)
# ---------------------------------------------------------------------------
def test_decorator_permits_when_role_grants_permission():
    user = FakeUser(FakeRole("cases:create"))

    @require_permission("cases:create", loader=lambda: user)
    def create_case():
        return "created"

    assert create_case() == "created"


def test_decorator_passes_through_arguments_on_permit():
    user = FakeUser(FakeRole("cases:create"))

    @require_permission("cases:create", loader=lambda: user)
    def create_case(name, *, owner):
        return f"{name}:{owner}"

    assert create_case("alpha", owner="analyst") == "alpha:analyst"


def test_decorator_exposes_guarded_permission():
    @require_permission("reports:export", loader=lambda: None)
    def export_report():  # pragma: no cover - body never runs in this test
        return "exported"

    assert export_report.required_permission == "reports:export"


# ---------------------------------------------------------------------------
# require_permission decorator — denied path (Requirement 23.5)
# ---------------------------------------------------------------------------
def test_decorator_denies_when_role_lacks_permission():
    user = FakeUser(FakeRole("cases:read"))

    @require_permission("cases:create", loader=lambda: user)
    def create_case():  # pragma: no cover - must not run when denied
        return "created"

    with pytest.raises(AuthorizationError) as exc_info:
        create_case()

    error = exc_info.value
    assert error.message == AUTHORIZATION_FAILURE_MESSAGE
    assert error.status_code == 403
    assert error.required_permission == "cases:create"


def test_decorator_denies_unauthenticated_principal():
    @require_permission("cases:create", loader=lambda: None)
    def create_case():  # pragma: no cover - must not run when denied
        return "created"

    with pytest.raises(AuthorizationError):
        create_case()


def test_decorator_denies_user_without_role():
    @require_permission("cases:create", loader=lambda: FakeUser(None))
    def create_case():  # pragma: no cover - must not run when denied
        return "created"

    with pytest.raises(AuthorizationError):
        create_case()


# ---------------------------------------------------------------------------
# Default loader resolves the principal from Flask's request-scoped g
# ---------------------------------------------------------------------------
def test_default_loader_reads_principal_from_flask_g():
    app = Flask(__name__)

    @require_permission("cases:create")
    def create_case():
        return "created"

    # Granted: g.current_user has a role with the permission.
    with app.test_request_context():
        g.current_user = FakeUser(FakeRole("cases:create"))
        assert create_case() == "created"

    # Denied: no authenticated principal on g.
    with app.test_request_context():
        with pytest.raises(AuthorizationError):
            create_case()
