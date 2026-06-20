"""AURALIS VISION application package.

Exposes the Flask application factory (``create_app``) and the shared Celery
application so the web tier and the async workers share a single configured
runtime.
"""
from __future__ import annotations

from flask import Flask

from app.config import Config, get_config
from app.extensions import celery_app, init_celery, init_db

__all__ = ["create_app", "celery_app"]


def create_app(config: dict | Config | None = None) -> Flask:
    """Application factory.

    Creates and configures the Flask application, binds Celery to the Flask
    application context, and registers all blueprints.

    Configuration is loaded from ``app/config.py`` (environment + secret store,
    Requirement 25.5). The ``config`` argument is an optional override that
    keeps the factory testable without external services: pass a ``Config``
    instance to replace the active environment's configuration, or a plain dict
    to layer per-key overrides on top of the loaded configuration.
    """
    app = Flask(__name__)

    # Load all settings from the environment / secret store. Nothing is
    # hard-coded here; secrets resolve through app.config.Config.
    if isinstance(config, Config):
        cfg = config
        app.config.from_object(config)
        app.config.update(config.as_dict())
    else:
        cfg = get_config()
        app.config.update(cfg.as_dict())
        if config:
            app.config.update(config)

    # Record the active environment name. ``Config.ENV_NAME`` is a class
    # attribute (not captured by ``as_dict``), so set it explicitly to keep the
    # value available regardless of how configuration was supplied.
    app.config["ENV_NAME"] = cfg.ENV_NAME

    # Bind Celery to the Flask application context.
    init_celery(app)

    # Bind the database session lifecycle to the application context. Engine
    # creation is deferred to first use, so this never opens a connection at
    # boot.
    init_db(app)

    # Register platform security controls (CSP, CSRF, rate limiting).
    from app.security.middleware import init_security

    init_security(app)

    # Register blueprints (route scaffolding).
    register_blueprints(app)

    # Register the platform health route.
    register_health_route(app)

    # Development convenience: when running against a local SQLite database
    # (no external Postgres), create the schema on boot so the app is usable
    # out of the box without running migrations or external services.
    _bootstrap_sqlite_schema(app)

    return app


def _bootstrap_sqlite_schema(app: Flask) -> None:
    """Create all tables when using a SQLite database (dev/test convenience)."""
    url = str(app.config.get("SQLALCHEMY_DATABASE_URI", ""))
    if not url.startswith("sqlite"):
        return
    try:
        import app.models  # noqa: F401 - register all models on Base.metadata
        from app.database import Base, get_engine

        Base.metadata.create_all(get_engine())
    except Exception:
        # Never let dev bootstrap block app creation.
        pass


def register_health_route(app: Flask) -> None:
    """Register the liveness/readiness health endpoint.

    ``GET /healthz`` confirms the application booted with its configuration
    loaded and that Celery and the database session factory are bound. It
    performs no I/O (no DB connection, no Celery round-trip) so it stays a fast,
    dependency-free liveness signal suitable for the reverse proxy and
    orchestrator (Requirement 21.2).
    """

    @app.get("/healthz")
    def healthz():
        return {
            "status": "ok",
            "environment": app.config.get("ENV_NAME"),
            "celery": "celery" in app.extensions,
            "database": "db" in app.extensions,
        }, 200

    @app.get("/")
    def index():
        # Land visitors on the dashboard.
        from flask import redirect

        return redirect("/ui/", code=302)


def register_blueprints(app: Flask) -> None:
    """Register all platform blueprints with the application.

    Blueprints are imported lazily inside this function so importing the app
    package never triggers a circular import, and so blueprint modules can
    depend on ``app`` helpers freely.
    """
    from app.blueprints import all_blueprints

    for blueprint in all_blueprints:
        app.register_blueprint(blueprint)
