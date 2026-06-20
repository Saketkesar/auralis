"""Flask blueprint registration scaffolding.

Each capability area is a separate blueprint. The factory imports
``all_blueprints`` and registers every entry, so adding a new capability area
means defining a blueprint module and appending it here, without touching the
app factory.
"""
from __future__ import annotations

from app.blueprints.auth import auth_bp
from app.blueprints.cases import cases_bp
from app.blueprints.graph import graph_bp
from app.blueprints.providers import providers_bp
from app.blueprints.reports import reports_bp
from app.blueprints.search import search_bp
from app.blueprints.ui import ui_bp

# Ordered collection of every blueprint the app factory should register.
all_blueprints = (
    auth_bp,
    cases_bp,
    search_bp,
    providers_bp,
    graph_bp,
    reports_bp,
    ui_bp,
)

__all__ = ["all_blueprints"]
