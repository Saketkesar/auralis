"""Celery worker entry point.

Workers start with ``celery -A app.worker.celery_app worker``. Importing this
module builds a Flask application so Celery is configured and bound to the
application context before any task runs.
"""
from __future__ import annotations

from app import celery_app, create_app

# Build the Flask app so init_celery configures the shared Celery instance and
# binds it to the application context.
flask_app = create_app()

__all__ = ["celery_app", "flask_app"]
