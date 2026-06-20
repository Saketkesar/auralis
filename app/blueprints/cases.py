"""Cases blueprint (Tasks 4.7, 7.1 dispatch, 14.3 CTF, 11.4 agent, 20.x).

Handles ingestion, case retrieval/reopen, status polling, CTF mode, hex view,
and the AI search agent. Ingestion accepts uploads and URLs, returns 202 on
accept and 400/413/415 with reasons on rejection.
"""
from __future__ import annotations

import uuid

from flask import Blueprint, current_app, jsonify, request

cases_bp = Blueprint("cases", __name__, url_prefix="/api/v1/cases")


def _session():
    db = current_app.extensions.get("db")
    return db() if db else None


def _ingestion():
    from app.services.audit import AuditLogService
    from app.services.ingestion_service import IngestionService

    session = _session()
    audit = AuditLogService(session) if session else None
    return IngestionService(session=session, config=dict(current_app.config), audit=audit)


@cases_bp.post("")
def create_case():
    """Ingest an image (file upload or URL) and start the pipeline."""
    service = _ingestion()

    results = []
    if request.files:
        for file in request.files.getlist("file") or list(request.files.values()):
            data = file.read()
            results.append(service.ingest_bytes(data, filename=file.filename))
    else:
        body = request.get_json(silent=True) or {}
        if body.get("url"):
            results.append(service.ingest_url(body["url"]))
        else:
            return jsonify({"error": "provide a file upload or a url"}), 400

    # Dispatch the pipeline for each accepted case.
    accepted = [r for r in results if r.accepted]
    from app.tasks.pipeline_tasks import dispatch_pipeline

    for r in accepted:
        try:
            dispatch_pipeline(r.case_id)
        except Exception:
            pass

    if not accepted:
        first = results[0]
        return jsonify({"error": first.message}), first.status_code

    payload = [
        {"case_id": str(r.case_id), "format": r.content_format, "accepted": r.accepted}
        for r in results
    ]
    return jsonify({"cases": payload}), 202


@cases_bp.get("/<uuid:case_id>")
def get_case(case_id: uuid.UUID):
    """Reopen a persisted case: restore findings and artifacts (26.5)."""
    session = _session()
    if session is None:
        return jsonify({"error": "no database"}), 503
    from app.models.artifact import Artifact
    from app.models.case import Case
    from app.models.stage_result import StageResult

    case = session.get(Case, case_id)
    if case is None:
        return jsonify({"error": "case not found"}), 404
    stages = session.query(StageResult).filter(StageResult.case_id == case_id).all()
    artifacts = session.query(Artifact).filter(Artifact.case_id == case_id).all()
    return jsonify(
        {
            "id": str(case.id),
            "status": case.status.value,
            "content_format": case.content_format,
            "stages": [
                {"stage": s.stage.value, "status": s.status.value, "findings": s.findings, "score": s.score}
                for s in stages
            ],
            "artifacts": [
                {"stage": a.stage.value, "kind": a.kind.value, "object_key": a.object_key}
                for a in artifacts
            ],
        }
    )


@cases_bp.get("/<uuid:case_id>/status")
def case_status(case_id: uuid.UUID):
    """Per-stage status; JSON for API, HTML fragment for HTMX polling (22.3)."""
    session = _session()
    stages = {}
    case_state = "unknown"
    if session is not None:
        from app.models.case import Case
        from app.models.stage_result import StageResult

        case = session.get(Case, case_id)
        case_state = case.status.value if case else "unknown"
        rows = session.query(StageResult).filter(StageResult.case_id == case_id).all()
        stages = {s.stage.value: s.status.value for s in rows}

    if request.headers.get("HX-Request"):
        from flask import render_template

        return render_template("_status.html", stages=stages)
    return jsonify({"case_status": case_state, "stages": stages})


@cases_bp.post("/<uuid:case_id>/ctf")
def run_ctf(case_id: uuid.UUID):
    """One-click CTF investigation (16.1)."""
    from app.engines.base import CaseContext, run_engine
    from app.forensics.ctf_engine import CTFEngine
    from app.services.storage import get_storage

    try:
        data = get_storage(dict(current_app.config)).get(f"{case_id}/original")
    except Exception:
        data = b""
    ctx = CaseContext(case_id=case_id, image_bytes=data, config=dict(current_app.config))
    result = run_engine(CTFEngine(), ctx)
    return jsonify({"stage": result.stage.value, "status": result.status.value, "findings": result.findings})


@cases_bp.get("/<uuid:case_id>/hex")
def hex_view(case_id: uuid.UUID):
    """Hex view of the raw image bytes (16.3)."""
    from app.forensics.ctf_engine import CTFEngine
    from app.services.storage import get_storage

    try:
        data = get_storage(dict(current_app.config)).get(f"{case_id}/original")
    except Exception:
        data = b""
    return jsonify({"hex": CTFEngine.hex_view(data)})


@cases_bp.get("/<uuid:case_id>/image")
def case_image(case_id: uuid.UUID):
    """Serve the original image bytes for the investigation viewer."""
    from flask import Response

    from app.services.storage import get_storage

    session = _session()
    mime = "image/jpeg"
    if session is not None:
        from app.models.case import Case

        case = session.get(Case, case_id)
        if case and case.content_format:
            mime = f"image/{case.content_format.lower()}"
    try:
        data = get_storage(dict(current_app.config)).get(f"{case_id}/original")
    except Exception:
        return jsonify({"error": "image not found"}), 404
    return Response(data, mimetype=mime)


@cases_bp.post("/<uuid:case_id>/public_url")
def case_public_url(case_id: uuid.UUID):
    """Upload the case image to a public temporary host and return direct URL."""
    from app.services.storage import get_storage
    import requests

    try:
        data = get_storage(dict(current_app.config)).get(f"{case_id}/original")
        if not data:
            return jsonify({"error": "image not found"}), 404

        files = {"file": ("image.jpg", data, "image/jpeg")}
        r = requests.post("https://tmpfiles.org/api/v1/upload", files=files, timeout=10)
        r.raise_for_status()
        res_json = r.json()
        if res_json.get("status") == "success":
            preview_url = res_json["data"]["url"]
            direct_url = preview_url.replace("tmpfiles.org/", "tmpfiles.org/dl/")
            return jsonify({"url": direct_url})
        return jsonify({"error": "failed to upload to temp host"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@cases_bp.post("/<uuid:case_id>/agent")
def run_agent(case_id: uuid.UUID):
    """Run the autonomous AI search agent (8.1)."""
    from app.engines.base import CaseContext, run_engine
    from app.geoint.ai_search_agent import AISearchAgent
    from app.services.storage import get_storage

    session = _session()
    prior = {}
    if session is not None:
        from app.models.stage_result import StageResult

        for s in session.query(StageResult).filter(StageResult.case_id == case_id).all():
            prior[s.stage] = s.findings or {}
    try:
        data = get_storage(dict(current_app.config)).get(f"{case_id}/original")
    except Exception:
        data = b""
    ctx = CaseContext(case_id=case_id, image_bytes=data, prior_findings=prior, config=dict(current_app.config))
    result = run_engine(AISearchAgent(), ctx)
    return jsonify({"stage": result.stage.value, "findings": result.findings})
