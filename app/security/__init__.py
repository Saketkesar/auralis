"""Security package: authentication, authorization, and request middleware.

This package implements Requirement 23 (authentication/authorization) and
Requirement 25 (platform security controls). The authentication service
(:mod:`app.security.auth`) validates Analyst credentials and issues/verifies
signed JWT session tokens.
"""
from __future__ import annotations

from app.security.auth import (
    AuthFailure,
    AuthSuccess,
    JwtAuthService,
    TokenClaims,
    TokenError,
    hash_password,
    verify_password,
)
from app.security.rbac import (
    AUTHORIZATION_FAILURE_MESSAGE,
    AuthorizationError,
    has_permission,
    permissions_for,
    require_permission,
)

__all__ = [
    "JwtAuthService",
    "AuthSuccess",
    "AuthFailure",
    "TokenClaims",
    "TokenError",
    "hash_password",
    "verify_password",
    "require_permission",
    "has_permission",
    "permissions_for",
    "AuthorizationError",
    "AUTHORIZATION_FAILURE_MESSAGE",
]
