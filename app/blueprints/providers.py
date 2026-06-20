"""Providers blueprint (Task 3.7).

Lists registered providers and toggles their enabled state (Requirement 6.6).
"""
from __future__ import annotations

from flask import Blueprint, jsonify, request

import app.search_providers.builtin  # noqa: F401 - self-registers providers
from app.services import provider_registry

providers_bp = Blueprint("providers", __name__, url_prefix="/api/v1/providers")


@providers_bp.get("")
def list_providers():
    return jsonify(
        [
            {
                "name": p.name,
                "category": p.category.value,
                "enabled": provider_registry.is_enabled(p.name),
            }
            for p in provider_registry.all_providers()
        ]
    )


@providers_bp.post("/<name>/enabled")
def set_enabled(name: str):
    body = request.get_json(silent=True) or {}
    enabled = bool(body.get("enabled", True))
    provider_registry.set_enabled(name, enabled)
    return jsonify({"name": name, "enabled": enabled})
