"""OpenSearch findings index client (Task 20.3; Requirements 26.2-26.4).

Indexes case findings after relational persistence. On indexing failure the
caller retains the persisted case and records the failure (26.3). Authorized
search returns only cases within the analyst's scope (26.4). Falls back to an
in-memory index when the OpenSearch client/server is unavailable.
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

try:  # optional dependency
    from opensearchpy import OpenSearch  # type: ignore

    _HAS_OS = True
except Exception:  # pragma: no cover
    OpenSearch = None  # type: ignore
    _HAS_OS = False

# In-memory fallback index: {case_id: document}
_MEMORY: Dict[str, Dict[str, Any]] = {}


class SearchIndex:
    def __init__(self, config: Optional[dict] = None) -> None:
        self._config = config or {}
        self._index = self._config.get("OPENSEARCH_INDEX", "cases")
        self._client = None
        if _HAS_OS and self._config.get("OPENSEARCH_HOSTS"):
            try:
                self._client = OpenSearch(hosts=self._config["OPENSEARCH_HOSTS"])
            except Exception:  # pragma: no cover
                self._client = None

    def index_case(self, case_id: uuid.UUID, owner_id: Optional[uuid.UUID], findings: Dict[str, Any]) -> bool:
        """Index a case's findings. Returns False on failure (caller retains case)."""
        doc = {
            "case_id": str(case_id),
            "owner_id": str(owner_id) if owner_id else None,
            "findings": findings,
        }
        try:
            if self._client is not None:
                self._client.index(index=self._index, id=str(case_id), body=doc)
            else:
                _MEMORY[str(case_id)] = doc
            return True
        except Exception:
            return False

    def search(self, query: str, *, authorized_owner_id: Optional[uuid.UUID]) -> List[Dict[str, Any]]:
        """Return matching cases the analyst is authorized to access (26.4)."""
        if self._client is not None:
            try:
                body = {
                    "query": {
                        "bool": {
                            "must": [{"query_string": {"query": query}}],
                            "filter": (
                                [{"term": {"owner_id": str(authorized_owner_id)}}]
                                if authorized_owner_id
                                else []
                            ),
                        }
                    }
                }
                hits = self._client.search(index=self._index, body=body)["hits"]["hits"]
                return [h["_source"] for h in hits]
            except Exception:
                pass
        # Fallback: check if we can query from DB, otherwise fall back to _MEMORY.
        db_results = []
        try:
            from flask import current_app, has_app_context
            if has_app_context():
                db = current_app.extensions.get("db")
                session = db() if db else None
                if session is not None:
                    from app.models.case import Case
                    from app.models.stage_result import StageResult
                    
                    query_obj = session.query(Case)
                    if authorized_owner_id:
                        query_obj = query_obj.filter(Case.owner_id == authorized_owner_id)
                    cases = query_obj.all()
                    for case in cases:
                        # Combine all findings for the case
                        flat_findings = {}
                        for stage_res in case.stage_results:
                            if stage_res.findings:
                                flat_findings[stage_res.stage.value] = stage_res.findings
                        # Check query
                        if query.lower() in str(flat_findings).lower():
                            db_results.append({
                                "case_id": str(case.id),
                                "owner_id": str(case.owner_id) if case.owner_id else None,
                                "findings": flat_findings
                            })
                    session.close()
                    return db_results
        except Exception:
            pass

        # Memory fallback: naive substring match + ownership filter.
        out = []
        for doc in _MEMORY.values():
            if authorized_owner_id and doc.get("owner_id") != str(authorized_owner_id):
                continue
            if query.lower() in str(doc.get("findings", "")).lower():
                out.append(doc)
        return out


def get_index(config: Optional[dict] = None) -> SearchIndex:
    try:
        from flask import current_app, has_app_context

        if config is None and has_app_context():
            config = dict(current_app.config)
    except Exception:
        pass
    return SearchIndex(config)


__all__ = ["SearchIndex", "get_index"]
