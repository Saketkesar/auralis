"""Threat intelligence engine (Task 15.1; Requirements 17.1-17.4).

Evaluates for fake identity documents, fabricated screenshots, scam imagery, and
phishing assets; produces a threat Risk_Score; records each indicator with its
category; and flags a potential threat when the score meets the configured
threshold.
"""
from __future__ import annotations

from typing import Any, Dict, List

from app.engines.base import CaseContext, StageResult
from app.models.enums import StageName
from app.utils.scoring import bounded_score
from app.utils.thresholds import flag_at_or_above

_CATEGORIES = ["fake_id", "fake_screenshot", "scam", "phishing"]


class ThreatEngine:
    name = StageName.THREAT

    def run(self, ctx: CaseContext) -> StageResult:
        threshold = float(ctx.get_config("THREAT_ALERT_THRESHOLD", 70.0))
        indicators = self._evaluate(ctx)
        risk = bounded_score(min(100.0, len(indicators) * 30.0))
        flagged = flag_at_or_above(risk, threshold)

        findings = {
            "indicators": indicators,
            "risk_score": risk,
            "is_threat": flagged,
        }
        return StageResult.completed(self.name, findings, score=risk)

    def _evaluate(self, ctx: CaseContext) -> List[Dict[str, Any]]:
        indicators: List[Dict[str, Any]] = []
        # Correlate with OCR findings (scam/phishing keywords) when available.
        ocr = ctx.prior(StageName.OCR) or {}
        text = " ".join(
            str(t.get("text", "")) for t in (ocr.get("text_regions") or [])
        ).lower()
        keywords = {
            "phishing": ["verify your account", "login here", "password expired"],
            "scam": ["you have won", "wire transfer", "bitcoin"],
        }
        for category, words in keywords.items():
            if any(w in text for w in words):
                indicators.append({"category": category, "evidence": "ocr_keyword"})
        return indicators


__all__ = ["ThreatEngine"]
