"""Search blueprint (Task 3.7 + 20.3).

Exposes multi-provider search through the Search Hub and an indexed-findings
query route. Importing the built-in providers self-registers them.
"""
from __future__ import annotations

from flask import Blueprint, jsonify, request

import app.search_providers.builtin  # noqa: F401 - self-registers providers
from app.search_providers.base import SearchRequest
from app.services.search_hub import SearchHub

search_bp = Blueprint("search", __name__, url_prefix="/api/v1/search")


@search_bp.post("/<category>")
def run_search(category: str):
    body = request.get_json(silent=True) or {}
    query = body.get("query")
    if not query:
        return jsonify({"error": "query is required"}), 400
    try:
        req = SearchRequest(query=query, category=category, limit=body.get("limit"))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    outcome = SearchHub().search(category, req)
    return jsonify(
        {
            "results": [
                {
                    "title": r.title,
                    "source": r.source,
                    "url": r.url,
                    "snippet": r.snippet,
                    "image_url": r.image_url,
                    "published_date": r.published_date.isoformat()
                    if r.published_date
                    else None,
                    "score": r.score,
                }
                for r in outcome.results
            ],
            "failures": [
                {"name": f.name, "reason": f.reason, "timed_out": f.timed_out}
                for f in outcome.failures
            ],
        }
    )


@search_bp.get("/find")
def find_cases():
    """Authorized indexed search over case findings (Requirement 26.4)."""
    from flask import current_app, g
    import uuid

    from app.services.search_index import get_index

    query = request.args.get("q", "")
    if not query:
        return jsonify({"results": []})
    owner_id = getattr(getattr(g, "current_user", None), "id", None)
    results = get_index(dict(current_app.config)).search(query, authorized_owner_id=owner_id)

    db = current_app.extensions.get("db")
    session = db() if db else None
    
    refined_results = []
    if session is not None:
        try:
            from app.models.case import Case
            for r in results:
                cid = r.get("case_id")
                if not cid:
                    continue
                try:
                    case_uuid = uuid.UUID(cid)
                except Exception:
                    continue
                case = session.get(Case, case_uuid)
                if case:
                    refined_results.append({
                        "id": str(case.id),
                        "status": case.status.value,
                        "format": case.content_format or "-",
                        "created": case.created_at.strftime("%Y-%m-%d %H:%M") if case.created_at else "-",
                    })
        except Exception:
            session.rollback()
        finally:
            session.close()

    # Fallback to returning simple results if database is not available
    if not refined_results and results:
        refined_results = [
            {
                "id": r.get("case_id"),
                "status": "complete",
                "format": "-",
                "created": "-",
            }
            for r in results
        ]

    return jsonify({"results": refined_results})
