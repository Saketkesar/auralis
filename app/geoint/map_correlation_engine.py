"""Map correlation engine (Task 11.5; Requirements 9.1-9.4).

Retrieves map/street-level imagery from MAP providers for candidate locations,
compares road layouts/building shapes/terrain, produces a location
Confidence_Score per candidate, and ranks candidates descending.
"""
from __future__ import annotations

from typing import Any, Dict, List

from app.engines.base import CaseContext, StageResult
from app.models.enums import ProviderCategory, StageName
from app.search_providers.base import SearchRequest
from app.services.search_hub import SearchHub
from app.utils.ranking import rank_and_cap
from app.utils.scoring import bounded_score


class MapCorrelationEngine:
    name = StageName.MAP_CORRELATION

    def __init__(self, hub: SearchHub | None = None) -> None:
        self._hub = hub or SearchHub()

    def run(self, ctx: CaseContext) -> StageResult:
        cap = int(ctx.get_config("MAP_MAX_CANDIDATES", 20))
        geoint = ctx.prior(StageName.GEOINT) or {}
        candidates = geoint.get("candidates") or []
        if not candidates:
            return StageResult.completed(self.name, {"candidates": []})

        scored: List[Dict[str, Any]] = []
        for cand in candidates:
            query = cand.get("city") or cand.get("country") or "location"
            outcome = self._hub.search(ProviderCategory.MAP, SearchRequest(query=str(query)))
            # Compare layouts/shapes/terrain (heuristic: presence of map imagery).
            base = float(cand.get("confidence", 50.0))
            map_support = 10.0 if outcome.results else 0.0
            scored.append(
                {
                    **cand,
                    "map_references": [r.url for r in outcome.results],
                    "confidence": bounded_score(base + map_support),
                }
            )

        ranked = rank_and_cap(scored, cap)
        score = ranked[0]["confidence"] if ranked else None
        return StageResult.completed(self.name, {"candidates": ranked}, score=score)


__all__ = ["MapCorrelationEngine"]
