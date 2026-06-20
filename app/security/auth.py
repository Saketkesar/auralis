"""JWT authentication service (Requirement 23.1, 23.2, 23.3).

This module implements the ``Authentication_Service`` from the design's Security
Architecture. It is responsible for three things:

* **Credential validation** — verifying a submitted password against the stored
  ``User.password_hash`` using a vetted password-hashing primitive
  (``werkzeug.security``, PBKDF2 by default). Passwords are never stored or
  compared in plaintext.
* **Token issuance** — on successful authentication, minting a *signed* JWT
  session token using the configured ``JWT_SECRET`` / ``JWT_ALGORITHM`` and an
  expiry of ``JWT_ACCESS_TOKEN_EXPIRES_SECONDS`` (Requirement 23.1).
* **Token verification** — validating the signature and expiry of a presented
  token so request handlers can authorise protected resources. A request that
  presents no token, an expired token, or a token with an invalid signature is
  denied (Requirement 23.3).

Invalid credentials are denied with an authentication failure *message* rather
than an exception, so callers (the auth blueprint, Task 5.10) can return a
uniform failure response without leaking which half of the credential pair was
wrong (Requirement 23.2).

The service is intentionally decoupled from Flask and the database: it operates
on a ``User``-like object supplied by the caller and a configuration passed at
construction. :meth:`JwtAuthService.from_config` adapts a mapping (e.g.
``flask.current_app.config``) into a service instance.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Mapping, Protocol

import jwt
from werkzeug.security import check_password_hash, generate_password_hash

# ---------------------------------------------------------------------------
# Password hashing helpers
# ---------------------------------------------------------------------------
# A non-empty placeholder hash compared against when no user (or no stored hash)
# is found. Verifying against it keeps the failure path's timing close to the
# success path's, mitigating user-enumeration via response timing.
_DUMMY_PASSWORD_HASH = generate_password_hash("auralis-vision-nonexistent-user")


def hash_password(password: str) -> str:
    """Return a salted, one-way hash of ``password`` for storage.

    Used when provisioning or updating an Analyst's credentials so that
    ``User.password_hash`` never contains a recoverable secret.
    """
    return generate_password_hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    """Return ``True`` iff ``password`` matches ``password_hash``.

    A missing/empty stored hash always fails, but the comparison is still run
    against a dummy hash so the rejection path does not return measurably faster
    than a real mismatch.
    """
    if not password_hash:
        # Run a comparison anyway to keep timing uniform, then reject.
        check_password_hash(_DUMMY_PASSWORD_HASH, password or "")
        return False
    return check_password_hash(password_hash, password or "")


# ---------------------------------------------------------------------------
# Credential-bearing user contract
# ---------------------------------------------------------------------------
class Credentialed(Protocol):
    """Minimal shape the auth service needs from a user record."""

    id: Any
    password_hash: str | None
    is_active: bool


# ---------------------------------------------------------------------------
# Result and claim types
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class TokenClaims:
    """Validated claims extracted from a verified session token."""

    subject: str
    role: str | None
    issued_at: datetime
    expires_at: datetime
    raw: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AuthSuccess:
    """Returned when credentials are valid; carries the signed token."""

    token: str
    claims: TokenClaims
    succeeded: bool = field(default=True, init=False)


@dataclass(frozen=True)
class AuthFailure:
    """Returned when credentials are invalid (Requirement 23.2)."""

    message: str
    succeeded: bool = field(default=False, init=False)


AuthResult = AuthSuccess | AuthFailure

# A single, non-specific message so the response never reveals whether the
# email or the password was the incorrect half (Requirement 23.2).
INVALID_CREDENTIALS_MESSAGE = "Invalid email or password."


class TokenError(Exception):
    """Raised when a presented token is missing, malformed, or invalid.

    Request handlers catch this to deny access to protected resources
    (Requirement 23.3).
    """


# ---------------------------------------------------------------------------
# Authentication service
# ---------------------------------------------------------------------------
class JwtAuthService:
    """Validates credentials, issues signed JWTs, and verifies tokens."""

    def __init__(
        self,
        *,
        secret: str,
        algorithm: str = "HS256",
        access_token_expires_seconds: int = 3600,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if not secret:
            raise ValueError("JWT secret must be a non-empty value")
        self._secret = secret
        self._algorithm = algorithm
        self._expires_seconds = int(access_token_expires_seconds)
        # Injectable clock keeps issuance/expiry deterministic under test.
        self._now = clock or (lambda: datetime.now(timezone.utc))

    @classmethod
    def from_config(cls, config: Mapping[str, Any]) -> "JwtAuthService":
        """Build a service from an app configuration mapping."""
        return cls(
            secret=config["JWT_SECRET"],
            algorithm=config.get("JWT_ALGORITHM", "HS256"),
            access_token_expires_seconds=config.get(
                "JWT_ACCESS_TOKEN_EXPIRES_SECONDS", 3600
            ),
        )

    # -- authentication --------------------------------------------------
    def authenticate(self, user: Credentialed | None, password: str) -> AuthResult:
        """Validate credentials and, on success, issue a signed token.

        Returns :class:`AuthSuccess` with a signed JWT when the user exists, is
        active, and the password matches the stored hash (Requirement 23.1).
        Otherwise returns :class:`AuthFailure` with a generic failure message
        (Requirement 23.2). A missing or inactive user is rejected with the same
        message and a dummy hash comparison to keep timing uniform.
        """
        if user is None:
            verify_password(password, None)  # uniform-timing rejection
            return AuthFailure(INVALID_CREDENTIALS_MESSAGE)
        if not getattr(user, "is_active", False):
            verify_password(password, None)
            return AuthFailure(INVALID_CREDENTIALS_MESSAGE)
        if not verify_password(password, getattr(user, "password_hash", None)):
            return AuthFailure(INVALID_CREDENTIALS_MESSAGE)

        token, claims = self._issue_token(user)
        return AuthSuccess(token=token, claims=claims)

    # -- token issuance --------------------------------------------------
    def issue_token(self, user: Credentialed) -> str:
        """Issue a signed JWT for an already-authenticated ``user``."""
        token, _ = self._issue_token(user)
        return token

    def _issue_token(self, user: Credentialed) -> tuple[str, TokenClaims]:
        issued_at = self._now().replace(microsecond=0)
        expires_at = issued_at + timedelta(seconds=self._expires_seconds)
        role = self._role_name(user)
        payload: dict[str, Any] = {
            "sub": str(user.id),
            "role": role,
            "type": "access",
            "iat": int(issued_at.timestamp()),
            "exp": int(expires_at.timestamp()),
        }
        token = jwt.encode(payload, self._secret, algorithm=self._algorithm)
        claims = TokenClaims(
            subject=payload["sub"],
            role=role,
            issued_at=issued_at,
            expires_at=expires_at,
            raw=payload,
        )
        return token, claims

    @staticmethod
    def _role_name(user: Credentialed) -> str | None:
        role = getattr(user, "role", None)
        if role is None:
            return None
        # Accept either a Role object with a ``name`` or a plain string.
        return getattr(role, "name", role) if not isinstance(role, str) else role

    # -- token verification ---------------------------------------------
    def verify_token(self, token: str | None) -> TokenClaims:
        """Verify a presented token's signature and expiry.

        Raises :class:`TokenError` when the token is absent, malformed, expired,
        or carries an invalid signature, so request handlers can deny access to
        protected resources (Requirement 23.3). On success returns the validated
        :class:`TokenClaims`.
        """
        if not token:
            raise TokenError("No session token was presented.")
        try:
            payload = jwt.decode(
                token,
                self._secret,
                algorithms=[self._algorithm],
                options={"require": ["exp", "iat", "sub"]},
            )
        except jwt.ExpiredSignatureError as exc:
            raise TokenError("Session token has expired.") from exc
        except jwt.InvalidTokenError as exc:
            raise TokenError("Session token is invalid.") from exc

        return TokenClaims(
            subject=str(payload["sub"]),
            role=payload.get("role"),
            issued_at=datetime.fromtimestamp(payload["iat"], tz=timezone.utc),
            expires_at=datetime.fromtimestamp(payload["exp"], tz=timezone.utc),
            raw=payload,
        )


__all__ = [
    "JwtAuthService",
    "AuthSuccess",
    "AuthFailure",
    "AuthResult",
    "TokenClaims",
    "TokenError",
    "INVALID_CREDENTIALS_MESSAGE",
    "hash_password",
    "verify_password",
]
