"""Smoke tests for the application factory and Celery binding (Task 1.1, 1.5).

These verify the enterprise scaffolding is wired correctly: the factory builds
an app with its configuration loaded, all blueprints register, the Celery app
is bound to the Flask application context, the database session factory is
bound, and the ``/healthz`` health route reports the app booted cleanly.
"""
from __future__ import annotations

from flask import Flask

from app import celery_app, create_app


def test_create_app_returns_flask_instance():
    app = create_app()
    assert isinstance(app, Flask)


def test_all_blueprints_registered():
    app = create_app()
    expected = {"auth", "cases", "search", "providers", "graph", "reports", "ui"}
    assert expected.issubset(set(app.blueprints))


def test_celery_bound_to_app_context():
    app = create_app({"CELERY_BROKER_URL": "redis://example:6379/0"})
    # init_celery stores the Celery app on the Flask extensions registry.
    assert app.extensions["celery"] is celery_app
    # Configuration flows from Flask config into Celery.
    assert celery_app.conf.broker_url == "redis://example:6379/0"


def test_celery_task_runs_in_app_context():
    create_app()
    from flask import current_app

    @celery_app.task
    def needs_app_context():
        # Accessing current_app proves a Flask app context is active.
        return current_app.name

    # Calling the task directly invokes FlaskTask.__call__, which pushes an
    # application context for the duration of the task.
    assert needs_app_context() == "app"


def test_config_loaded_into_app():
    """The factory boots with the loaded configuration applied to the app."""
    app = create_app()
    # Values sourced from app.config.Config.as_dict() are present on the app.
    assert app.config.get("ENV_NAME")
    assert app.config.get("MAX_FILE_SIZE")
    # Per-key overrides layer on top of the loaded configuration.
    overridden = create_app({"MAX_FILE_SIZE": 123})
    assert overridden.config["MAX_FILE_SIZE"] == 123


def test_database_session_factory_bound():
    """init_db binds a request-scoped session factory without opening a connection."""
    app = create_app()
    assert "db" in app.extensions
    assert callable(app.extensions["db"])


def test_healthz_reports_ok_with_bound_extensions():
    """The health route boots cleanly and reports config + bound extensions."""
    app = create_app()
    client = app.test_client()

    response = client.get("/healthz")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "ok"
    assert payload["environment"] == app.config.get("ENV_NAME")
    assert payload["celery"] is True
    assert payload["database"] is True
