"""Authentication blueprint (Task 5.10; Requirements 23.1-23.3).

Exposes login and logout. Login validates credentials and issues a signed JWT;
invalid credentials return an authentication failure message.
"""
from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

from app.security.auth import AuthFailure, AuthSuccess, JwtAuthService

auth_bp = Blueprint("auth", __name__, url_prefix="/api/v1/auth")


def _lookup_user(email: str):
    """Resolve a user by email from the DB session if one is bound."""
    db = current_app.extensions.get("db")
    if db is None:
        return None
    session = db()
    from app.models.user import User

    return session.query(User).filter(User.email == email).one_or_none()


@auth_bp.post("/login")
def login():
    body = request.get_json(silent=True) or {}
    email = body.get("email", "")
    password = body.get("password", "")

    service = JwtAuthService.from_config(current_app.config)
    user = _lookup_user(email)
    result = service.authenticate(user, password)

    if isinstance(result, AuthSuccess):
        return jsonify({"token": result.token, "token_type": "bearer"}), 200
    message = result.message if isinstance(result, AuthFailure) else "Authentication failed."
    return jsonify({"error": message}), 401


@auth_bp.post("/logout")
def logout():
    # Stateless JWT: logout is a client-side token discard. Endpoint provided
    # for symmetry and audit logging.
    return jsonify({"status": "logged_out"}), 200
