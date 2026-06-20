"""UI blueprint (Tasks 19.1-19.4).

Server-rendered dashboard and tabbed investigation view (Jinja2 + Tailwind +
AlpineJS + HTMX + Cytoscape). The investigation view polls stage status via
HTMX and renders the knowledge graph with Cytoscape.
"""
from __future__ import annotations

import uuid

from flask import Blueprint, current_app, render_template

ui_bp = Blueprint(
    "ui",
    __name__,
    url_prefix="/ui",
    template_folder="../templates",
    static_folder="../static",
)


def _session():
    db = current_app.extensions.get("db")
    return db() if db else None


@ui_bp.get("/")
def dashboard():
    session = _session()
    recent = []
    counts = {
        "cases": 0,
        "deepfakes": 0,
        "ai_images": 0,
        "stego": 0,
        "threat": 0,
    }
    if session is not None:
        try:
            from app.models.case import Case
            from app.models.enums import StageName, StageStatus
            from app.models.stage_result import StageResult

            cases = session.query(Case).order_by(Case.created_at.desc()).limit(10).all()
            counts["cases"] = session.query(Case).count()
            recent = [
                {
                    "id": str(c.id),
                    "status": c.status.value,
                    "format": c.content_format or "-",
                    "created": c.created_at.strftime("%Y-%m-%d %H:%M") if c.created_at else "-",
                }
                for c in cases
            ]

            # Dynamic authentic counts
            deepfake_rows = session.query(StageResult).filter(
                StageResult.stage == StageName.DEEPFAKE,
                StageResult.status == StageStatus.COMPLETED
            ).all()
            counts["deepfakes"] = sum(1 for r in deepfake_rows if r.findings and r.findings.get("is_deepfake"))

            ai_rows = session.query(StageResult).filter(
                StageResult.stage == StageName.AI_IMAGE,
                StageResult.status == StageStatus.COMPLETED
            ).all()
            counts["ai_images"] = sum(1 for r in ai_rows if r.findings and r.findings.get("is_ai_generated"))

            stego_rows = session.query(StageResult).filter(
                StageResult.stage == StageName.STEGO,
                StageResult.status == StageStatus.COMPLETED
            ).all()
            counts["stego"] = sum(1 for r in stego_rows if r.findings and r.findings.get("hidden_data"))

            threat_rows = session.query(StageResult).filter(
                StageResult.stage == StageName.THREAT,
                StageResult.status == StageStatus.COMPLETED
            ).all()
            counts["threat"] = sum(1 for r in threat_rows if r.findings and r.findings.get("is_threat"))

        except Exception:
            # DB unavailable (e.g. local run without Postgres): render empty.
            session.rollback() if hasattr(session, "rollback") else None
            recent = []
    cards = [
        {"label": "Total Cases", "value": counts["cases"]},
        {"label": "Images Processed", "value": counts["cases"]},
        {"label": "Deepfakes Found", "value": counts["deepfakes"]},
        {"label": "AI Images Found", "value": counts["ai_images"]},
        {"label": "Stego Findings", "value": counts["stego"]},
        {"label": "Threat Findings", "value": counts["threat"]},
    ]
    return render_template("dashboard.html", cards=cards, recent=recent)


@ui_bp.get("/cases/<uuid:case_id>")
def investigation(case_id: uuid.UUID):
    return render_template("investigation.html", case_id=str(case_id))


@ui_bp.get("/cases")
def cases_list():
    return dashboard()


@ui_bp.get("/settings")
def settings():
    return render_template("dashboard.html", cards=[], recent=[])
