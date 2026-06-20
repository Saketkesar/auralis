"""Autonomous AI search agent (Task 11.4; Requirements 8.1-8.5).

Analyzes the image plus existing findings, generates derived search queries,
executes them through the Search Hub, ranks results, and returns at most the top
20 candidate locations each with a Confidence_Score.
"""
from __future__ import annotations

from typing import Any, Dict, List

from app.engines.base import CaseContext, StageResult
from app.models.enums import ProviderCategory, StageName
from app.search_providers.base import SearchRequest
from app.services.search_hub import SearchHub
from app.utils.ranking import rank_and_cap


class AISearchAgent:
    name = StageName.AI_SEARCH_AGENT

    def __init__(self, hub: SearchHub | None = None) -> None:
        self._hub = hub or SearchHub()

    def run(self, ctx: CaseContext) -> StageResult:
        cap = int(ctx.get_config("AI_AGENT_MAX_CANDIDATES", 20))
        queries = self._generate_queries(ctx)
        candidates: List[Dict[str, Any]] = []
        for q in queries:
            outcome = self._hub.search(ProviderCategory.GENERAL, SearchRequest(query=q))
            for r in outcome.results:
                candidates.append(
                    {
                        "label": r.title,
                        "url": r.url,
                        "query": q,
                        "confidence": float(r.score or 0.0),
                    }
                )
        ranked = rank_and_cap(candidates, cap)
        findings = {"queries": queries, "candidates": ranked}
        return StageResult.completed(self.name, findings)

    def _generate_queries(self, ctx: CaseContext) -> List[str]:
        """Derive search queries from OCR text, objects, and landmarks."""
        terms: List[str] = []
        ocr = ctx.prior(StageName.OCR) or {}
        for region in (ocr.get("text_regions") or [])[:5]:
            text = str(region.get("text", "")).strip()
            if text:
                terms.append(text)
        obj = ctx.prior(StageName.OBJECT) or {}
        for klass in (obj.get("inventory") or {}):
            terms.append(str(klass))
        landmark = ctx.prior(StageName.LANDMARK) or {}
        for m in (landmark.get("matches") or [])[:3]:
            if m.get("name"):
                terms.append(str(m["name"]))

        if not terms:
            return []
        # Compose a few combined queries from the discovered terms.
        queries = [" ".join(terms[:3])]
        if len(terms) > 1:
            queries.append(" near ".join(terms[:2]))
        return [q for q in queries if q.strip()]


__all__ = ["AISearchAgent"]
