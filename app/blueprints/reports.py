"""Reports blueprint (Task 18.4; Requirements 20.1, 20.3, 20.4)."""
from __future__ import annotations

import uuid

from flask import Blueprint, current_app, jsonify, request, Response

from app.reports.report_service import NoFindingsError, compile_report, render

reports_bp = Blueprint("reports", __name__, url_prefix="/api/v1/cases")


def _session():
    db = current_app.extensions.get("db")
    return db() if db else None


@reports_bp.post("/<uuid:case_id>/report")
def generate_report(case_id: uuid.UUID):
    fmt = (request.get_json(silent=True) or {}).get("format", "json")
    session = _session()
    rows = []
    if session is not None:
        from app.models.stage_result import StageResult

        rows = session.query(StageResult).filter(StageResult.case_id == case_id).all()

    try:
        report = compile_report(case_id, rows)
    except NoFindingsError as exc:
        return jsonify({"error": str(exc)}), 409

    try:
        data, mime = render(report, fmt)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    return Response(
        data,
        mimetype=mime,
        headers={"Content-Disposition": f"attachment; filename=report-{case_id}.{fmt}"},
    )
