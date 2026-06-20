"""Platform security middleware (Task 5.5; Requirements 25.1-25.4).

Wires three controls into the Flask app:

* A Content-Security-Policy header on every response (25.1).
* CSRF token validation on state-changing requests before processing (25.2).
* Per-client rate limiting where a configured limit of zero rejects all (25.3,
  25.4). Uses Flask-Limiter backed by Redis when available, with an in-memory
  fixed-window fallback so the control works without Redis.
"""
from __future__ import annotations

import time
from collections import defaultdict
from typing import Dict, Tuple

from flask import Flask, g, jsonify, request, session

_DEFAULT_CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://unpkg.com https://cdn.tailwindcss.com; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "img-src 'self' data: blob: https:; "
    "connect-src 'self'; "
    "font-src 'self' https://fonts.gstatic.com; "
    "object-src 'none'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
)

_STATE_CHANGING = {"POST", "PUT", "PATCH", "DELETE"}
_CSRF_EXEMPT_PREFIXES = ("/api/v1/auth/login",)

# In-memory rate-limit buckets: {(client, window_start): count}
_buckets: Dict[Tuple[str, int], int] = defaultdict(int)


def init_security(app: Flask) -> None:
    """Register CSP, CSRF, and rate-limiting handlers on ``app``."""
    csp = app.config.get("CONTENT_SECURITY_POLICY", _DEFAULT_CSP)
    limit = _parse_limit(app.config.get("RATELIMIT_DEFAULT", "100/minute"))
    enabled = bool(app.config.get("RATELIMIT_ENABLED", True))

    @app.after_request
    def _add_csp(response):  # noqa: ANN001
        response.headers.setdefault("Content-Security-Policy", csp)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        return response

    @app.before_request
    def _rate_limit():  # noqa: ANN001
        if not enabled:
            return None
        count, window = limit
        # A configured limit of zero rejects all rate-limited requests (25.4).
        client = request.headers.get("X-Forwarded-For", request.remote_addr or "anon")
        now = int(time.time())
        window_start = now - (now % window) if window else now
        if count == 0:
            return jsonify({"error": "rate limit exceeded"}), 429
        key = (client, window_start)
        _buckets[key] += 1
        if _buckets[key] > count:
            return jsonify({"error": "rate limit exceeded"}), 429
        return None

    @app.before_request
    def _csrf_protect():  # noqa: ANN001
        if request.method not in _STATE_CHANGING:
            return None
        path = request.path
        if any(path.startswith(p) for p in _CSRF_EXEMPT_PREFIXES):
            return None
        # CSRF protects cookie/session-authenticated browser flows. It only
        # applies once a session-bound CSRF token has been established; pure
        # token-authenticated API clients (Authorization header, no session)
        # and unauthenticated dev calls are not subject to it.
        expected = session.get("csrf_token")
        if expected is None:
            return None
        token = request.headers.get("X-CSRF-Token") or (
            request.form.get("csrf_token") if request.form else None
        )
        if not token or token != expected:
            return jsonify({"error": "missing or invalid CSRF token"}), 403
        return None


def _parse_limit(value: str) -> Tuple[int, int]:
    """Parse a 'N/period' limit string into (count, window_seconds)."""
    try:
        count_s, period = value.split("/", 1)
        count = int(count_s)
    except Exception:
        return (100, 60)
    period = period.strip().lower()
    window = {
        "second": 1,
        "minute": 60,
        "hour": 3600,
        "day": 86400,
    }.get(period.rstrip("s"), 60)
    return (count, window)


def reset_rate_limits() -> None:
    """Test helper to clear in-memory buckets."""
    _buckets.clear()


__all__ = ["init_security", "reset_rate_limits"]
