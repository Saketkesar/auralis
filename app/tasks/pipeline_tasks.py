"""Celery task wrappers for the investigation pipeline (Task 7.1).

In production the pipeline is dispatched to Celery (Redis broker) and fans out
across CPU/GPU workers. For local/dev runs without a broker, ``dispatch_pipeline``
falls back to running the pipeline in a background thread so the HTTP request
returns immediately and the stages still execute.
"""
from __future__ import annotations

import threading
import uuid

from app.extensions import celery_app


@celery_app.task(name="auralis.run_pipeline", queue="cpu")
def run_pipeline_task(case_id: str) -> dict:
    """Run the full analysis pipeline for a case (Celery entry point)."""
    from flask import current_app

    from app.services.pipeline_orchestrator import PipelineOrchestrator

    db = current_app.extensions.get("db")
    session = db() if db else None
    orchestrator = PipelineOrchestrator(session=session, config=dict(current_app.config))
    return orchestrator.run_pipeline(uuid.UUID(case_id))


def _run_in_thread(app, case_id: uuid.UUID) -> None:
    def _target():
        with app.app_context():
            from app.database import get_sessionmaker
            from app.services.pipeline_orchestrator import PipelineOrchestrator

            session = get_sessionmaker()()
            try:
                PipelineOrchestrator(
                    session=session, config=dict(app.config)
                ).run_pipeline(case_id)
            finally:
                session.close()

    threading.Thread(target=_target, daemon=True).start()


def dispatch_pipeline(case_id: uuid.UUID) -> None:
    """Enqueue the pipeline on Celery, or run it in-process if no broker.

    By default (local/dev) the pipeline runs in a background thread so there is
    no broker dependency. Set ``AURALIS_USE_CELERY=1`` to publish to the broker
    for a real worker deployment.
    """
    import os

    from flask import current_app

    app = current_app._get_current_object()
    if os.environ.get("AURALIS_USE_CELERY") == "1":
        try:
            run_pipeline_task.apply_async(args=[str(case_id)], retry=False)
            return
        except Exception:
            pass
    _run_in_thread(app, case_id)


__all__ = ["run_pipeline_task", "dispatch_pipeline"]
