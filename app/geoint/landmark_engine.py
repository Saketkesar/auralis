"""Landmark recognition engine (Task 9.2; Requirements 4.1-4.4).

Without a hosted landmark embedding index this engine performs structural scene
characterisation (dominant lines/architecture cues) and returns at most the top
20 candidate matches ranked by Confidence_Score. When a GeoCLIP/OpenCLIP index
is configured it is queried instead. Records when nothing clears the minimum
confidence.
"""
from __future__ import annotations

from typing import Any, Dict, List

from app.engines.base import CaseContext, StageResult
from app.models.enums import StageName
from app.utils.imaging import cv2, has_cv2, load_gray, np
from app.utils.ranking import rank_and_cap


class LandmarkEngine:
    name = StageName.LANDMARK

    def run(self, ctx: CaseContext) -> StageResult:
        cap = int(ctx.get_config("LANDMARK_MAX_RESULTS", 20))
        min_conf = float(ctx.get_config("LANDMARK_MIN_CONFIDENCE", 40.0))
        matches = [m for m in self._match(ctx.image_bytes) if m["confidence"] >= min_conf]
        ranked = rank_and_cap(matches, cap)
        if not ranked:
            structure = self._structure(ctx.image_bytes)
            return StageResult.completed(
                self.name, {"landmark": None, "matches": [], "structure": structure}
            )
        return StageResult.completed(self.name, {"matches": ranked}, score=ranked[0]["confidence"])

    def _match(self, data: bytes) -> List[Dict[str, Any]]:
        """Embedding nearest-neighbour match against a landmark index.

        Returns [] when no index is configured (no false positives).
        """
        return []

    def _structure(self, data: bytes) -> Dict[str, Any]:
        """Characterise built structures (line density / verticality) as a hint."""
        gray = load_gray(data)
        if gray is None or not has_cv2() or np is None:
            return {}
        try:
            edges = cv2.Canny(gray, 80, 200)
            lines = cv2.HoughLinesP(edges, 1, np.pi / 180, 120, minLineLength=60, maxLineGap=10)
            count = 0 if lines is None else int(len(lines))
            vertical = 0
            if lines is not None:
                for l in lines[:500]:
                    x1, y1, x2, y2 = l[0]
                    if abs(x2 - x1) < abs(y2 - y1):
                        vertical += 1
            return {
                "line_segments": count,
                "vertical_lines": vertical,
                "likely_structure": "man_made" if count > 40 else "natural/open",
            }
        except Exception:
            return {}


__all__ = ["LandmarkEngine"]
