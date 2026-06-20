"""Shared extension instances and the Celery integration.

These objects are instantiated here without an application bound to them so
they can be imported anywhere without triggering circular imports. They are
wired to the Flask application inside the app factory (``create_app``).
"""
from __future__ import annotations

from celery import Celery

# A single Celery instance shared across the platform. It is configured and
# bound to the Flask application context inside ``create_app`` via
# ``init_celery``.
celery_app = Celery("auralis_vision")


def init_db(app):
    """Bind the database session lifecycle to the Flask application.

    The shared engine and session factory live in :mod:`app.database.session`
    and are created lazily on first use, so this binding never opens a
    connection (or requires a database driver to be importable) at app-boot
    time — the app and its health check come up cleanly without a database.

    Wiring performed here:

    - Exposes a request-scoped session factory at ``app.extensions["db"]``.
      Calling it returns a ``scoped_session`` whose underlying engine is
      created on first access.
    - Registers a ``teardown_appcontext`` handler that removes the scoped
      session at the end of each application context so connections are
      returned to the pool and no session leaks across requests/tasks.
    """
    from sqlalchemy.orm import scoped_session

    from app.database.session import get_sessionmaker

    # Holds the scoped_session once it is first requested. Deferring creation
    # keeps engine/driver resolution lazy (Requirement 26.1 binding without a
    # boot-time connection).
    registry: dict[str, object] = {"scoped": None}

    def session_factory():
        if registry["scoped"] is None:
            registry["scoped"] = scoped_session(get_sessionmaker())
        return registry["scoped"]

    app.extensions["db"] = session_factory

    @app.teardown_appcontext
    def _remove_session(exception=None):  # noqa: ANN001 - Flask callback signature
        scoped = registry["scoped"]
        if scoped is not None:
            scoped.remove()

    return session_factory


def init_celery(app) -> Celery:
    """Bind the Celery app to the Flask application context.

    Every task executes inside a Flask application context so tasks can use
    application configuration, the database session, and other extensions just
    like a request handler would.
    """
    celery_app.conf.update(
        broker_url=app.config.get("CELERY_BROKER_URL", "redis://localhost:6379/0"),
        result_backend=app.config.get(
            "CELERY_RESULT_BACKEND", "redis://localhost:6379/1"
        ),
        task_default_queue=app.config.get("CELERY_TASK_DEFAULT_QUEUE", "cpu"),
    )

    class FlaskTask(celery_app.Task):
        """Base task that pushes a Flask application context on execution."""

        abstract = True

        def __call__(self, *args, **kwargs):
            with app.app_context():
                return super().__call__(*args, **kwargs)

    celery_app.Task = FlaskTask
    app.extensions["celery"] = celery_app
    return celery_app
