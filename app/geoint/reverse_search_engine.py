"""Reverse image search correlation engine (Task 11.1; Requirements 7.1-7.6).

Submits the image to IMAGE providers via the Search Hub, classifies results as
exact/near matches, identifies the oldest appearance, records the website set,
builds a date-ordered timeline, and records when no matches are found.
"""
from __future__ import annotations

from typing import Any, Dict, List
from urllib.parse import urlparse

from app.engines.base import CaseContext, StageResult
from app.models.enums import ProviderCategory, StageName
from app.search_providers.base import SearchRequest
from app.services.search_hub import SearchHub

_EXACT_SIMILARITY = 0.9


class ReverseSearchEngine:
    name = StageName.REVERSE_SEARCH

    def __init__(self, hub: SearchHub | None = None) -> None:
        self._hub = hub or SearchHub()

    def run(self, ctx: CaseContext) -> StageResult:
        request = SearchRequest(image_bytes=ctx.image_bytes, category=ProviderCategory.IMAGE)
        outcome = self._hub.search(ProviderCategory.IMAGE, request)
        results = outcome.results
        if not results:
            return StageResult.completed(self.name, {"matches": None})

        matches: List[Dict[str, Any]] = []
        for r in results:
            similarity = float(r.raw.get("similarity", 0.0)) if r.raw else 0.0
            matches.append(
                {
                    "title": r.title,
                    "url": r.url,
                    "source": r.source,
                    "similarity": similarity,
                    "match_type": "exact" if similarity >= _EXACT_SIMILARITY else "near",
                    "published_date": r.published_date.isoformat() if r.published_date else None,
                }
            )

        websites = sorted({urlparse(m["url"]).netloc for m in matches if m["url"]})
        dated = [m for m in matches if m["published_date"]]
        oldest = min(dated, key=lambda m: m["published_date"]) if dated else None
        timeline = sorted(dated, key=lambda m: m["published_date"])

        findings = {
            "matches": matches,
            "websites": websites,
            "oldest_appearance": oldest,
            "timeline": timeline,
            "provider_failures": [f.name for f in outcome.failures],
        }
        return StageResult.completed(self.name, findings)


__all__ = ["ReverseSearchEngine"]
