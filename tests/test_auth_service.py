"""Unit tests for the JWT authentication service (Task 5.1).

Covers credential validation, signed-token issuance, and token verification
against Requirements 23.1 (authenticate + issue signed token), 23.2 (deny
invalid credentials with a failure message), and 23.3 (deny protected access
without a valid token).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pytest

from app.security.auth import (
    INVALID_CREDENTIALS_MESSAGE,
    AuthFailure,
    AuthSuccess,
    JwtAuthService,
    TokenError,
    hash_password,
    verify_password,
)

SECRET = "unit-test-secret-value"
ALGORITHM = "HS256"


class FakeRole:
    def __init__(self, name: str) -> None:
        self.name = name


class FakeUser:
    """A minimal stand-in for the ORM ``User`` (no DB required)."""

    def __init__(
        self,
        *,
        password: str = "correct horse battery staple",
        is_active: bool = True,
        role: object | None = None,
    ) -> None:
        self.id = uuid.uuid4()
        self.password_hash = hash_password(password)
        self.is_active = is_active
        self.role = role


@pytest.fixture
def service() -> JwtAuthService:
    return JwtAuthService(
        secret=SECRET,
        algorithm=ALGORITHM,
        access_token_expires_seconds=3600,
    )


# ---------------------------------------------------------------------------
# Password hashing helpers
# ---------------------------------------------------------------------------
def test_hash_password_is_not_plaintext_and_verifies():
    hashed = hash_password("s3cret")
    assert hashed != "s3cret"
    assert verify_password("s3cret", hashed) is True
    assert verify_password("wrong", hashed) is False


def test_verify_password_with_missing_hash_is_false():
    assert verify_password("anything", None) is False
    assert verify_password("anything", "") is False


# ---------------------------------------------------------------------------
# Requirement 23.1 — valid credentials authenticate and issue a signed token
# ---------------------------------------------------------------------------
def test_valid_login_issues_signed_token(service: JwtAuthService):
    user = FakeUser(password="hunter2", role=FakeRole("analyst"))

    result = service.authenticate(user, "hunter2")

    assert isinstance(result, AuthSuccess)
    assert result.succeeded is True
    assert result.token

    # The token is genuinely signed: decoding with the secret succeeds and the
    # claims describe this user.
    decoded = jwt.decode(result.token, SECRET, algorithms=[ALGORITHM])
    assert decoded["sub"] == str(user.id)
    assert decoded["role"] == "analyst"
    assert decoded["type"] == "access"
    assert decoded["exp"] > decoded["iat"]


def test_token_signature_depends_on_secret(service: JwtAuthService):
    user = FakeUser(password="pw")
    token = service.authenticate(user, "pw").token

    with pytest.raises(jwt.InvalidSignatureError):
        jwt.decode(token, "a-different-secret", algorithms=[ALGORITHM])


def test_role_is_null_when_user_has_no_role(service: JwtAuthService):
    user = FakeUser(password="pw", role=None)
    result = service.authenticate(user, "pw")
    assert isinstance(result, AuthSuccess)
    assert result.claims.role is None


# ---------------------------------------------------------------------------
# Requirement 23.2 — invalid credentials are denied with a failure message
# ---------------------------------------------------------------------------
def test_wrong_password_is_denied_with_message(service: JwtAuthService):
    user = FakeUser(password="right")

    result = service.authenticate(user, "wrong")

    assert isinstance(result, AuthFailure)
    assert result.succeeded is False
    assert result.message == INVALID_CREDENTIALS_MESSAGE


def test_unknown_user_is_denied_with_message(service: JwtAuthService):
    result = service.authenticate(None, "whatever")

    assert isinstance(result, AuthFailure)
    assert result.message == INVALID_CREDENTIALS_MESSAGE


def test_inactive_user_is_denied_even_with_correct_password(service: JwtAuthService):
    user = FakeUser(password="pw", is_active=False)

    result = service.authenticate(user, "pw")

    assert isinstance(result, AuthFailure)
    assert result.message == INVALID_CREDENTIALS_MESSAGE


def test_failure_message_does_not_reveal_which_field_was_wrong(service: JwtAuthService):
    # Same message whether the user is unknown or the password is wrong.
    unknown = service.authenticate(None, "pw")
    bad_pw = service.authenticate(FakeUser(password="right"), "wrong")
    assert unknown.message == bad_pw.message


# ---------------------------------------------------------------------------
# Requirement 23.3 — token verification gates protected resources
# ---------------------------------------------------------------------------
def test_verify_token_round_trips_valid_token(service: JwtAuthService):
    user = FakeUser(password="pw", role=FakeRole("admin"))
    token = service.authenticate(user, "pw").token

    claims = service.verify_token(token)

    assert claims.subject == str(user.id)
    assert claims.role == "admin"
    assert claims.expires_at > claims.issued_at


def test_verify_token_rejects_missing_token(service: JwtAuthService):
    with pytest.raises(TokenError):
        service.verify_token(None)
    with pytest.raises(TokenError):
        service.verify_token("")


def test_verify_token_rejects_malformed_token(service: JwtAuthService):
    with pytest.raises(TokenError):
        service.verify_token("not.a.jwt")


def test_verify_token_rejects_bad_signature(service: JwtAuthService):
    forged = jwt.encode(
        {
            "sub": "x",
            "iat": int(datetime.now(timezone.utc).timestamp()),
            "exp": int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
        },
        "attacker-secret",
        algorithm=ALGORITHM,
    )
    with pytest.raises(TokenError):
        service.verify_token(forged)


def test_verify_token_rejects_expired_token():
    past = datetime(2000, 1, 1, tzinfo=timezone.utc)
    expired_service = JwtAuthService(
        secret=SECRET,
        algorithm=ALGORITHM,
        access_token_expires_seconds=60,
        clock=lambda: past,
    )
    token = expired_service.issue_token(FakeUser(password="pw"))

    # Verify with a service whose clock is "now" (long after expiry).
    verifier = JwtAuthService(secret=SECRET, algorithm=ALGORITHM)
    with pytest.raises(TokenError):
        verifier.verify_token(token)


def test_from_config_builds_equivalent_service():
    config = {
        "JWT_SECRET": SECRET,
        "JWT_ALGORITHM": ALGORITHM,
        "JWT_ACCESS_TOKEN_EXPIRES_SECONDS": 1800,
    }
    svc = JwtAuthService.from_config(config)
    user = FakeUser(password="pw")
    token = svc.authenticate(user, "pw").token
    claims = svc.verify_token(token)
    assert claims.subject == str(user.id)
