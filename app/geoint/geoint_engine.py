"""GEOINT location inference engine (Task 9.1; Requirements 3.1-3.5).

Detects geographic cues by combining (1) GPS from metadata, (2) location clues
from OCR, and (3) a vision-based scene/terrain classifier (vegetation, sky/water,
built-up area, snow/sand) derived from real colour statistics. Produces ranked
country/state/city candidates each with a Confidence_Score, and records when no
inference is possible.
"""
from __future__ import annotations

from typing import Any, Dict, List

from app.engines.base import CaseContext, StageResult
from app.models.enums import StageName
from app.utils.imaging import cv2, has_cv2, load_array, np
from app.utils.ranking import rank_and_cap


class GeointEngine:
    name = StageName.GEOINT

    def run(self, ctx: CaseContext) -> StageResult:
        cap = int(ctx.get_config("GEOINT_MAX_CANDIDATES", 20))
        scene = self._scene(ctx.image_bytes)
        cues = self._detect_cues(ctx, scene)
        if not cues:
            return StageResult.completed(
                self.name, {"location_inference": None, "cues": [], "scene": scene}
            )

        candidates = self._candidates(ctx, scene)
        ranked = rank_and_cap(candidates, cap)
        findings = {"cues": cues, "scene": scene, "candidates": ranked}
        score = ranked[0]["confidence"] if ranked else None
        return StageResult.completed(self.name, findings, score=score)

    def _scene(self, data: bytes) -> Dict[str, Any]:
        arr = load_array(data)
        if arr is None or not has_cv2() or np is None:
            return {}
        try:
            hsv = cv2.cvtColor(arr, cv2.COLOR_RGB2HSV)
            h, s, v = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
            total = h.size
            green = float(((h > 35) & (h < 85) & (s > 40)).sum()) / total
            blue = float(((h > 90) & (h < 130) & (s > 40)).sum()) / total
            gray = float((s < 30).sum()) / total
            bright = float((v > 200).sum()) / total
            tags = []
            if green > 0.25:
                tags.append("vegetation")
            if blue > 0.15:
                tags.append("sky_or_water")
            if gray > 0.4:
                tags.append("built_up_or_overcast")
            if bright > 0.4:
                tags.append("snow_or_sand")
            terrain = (
                "rural/natural" if green > 0.3 else "urban" if gray > 0.45 else "mixed"
            )
            return {
                "tags": tags,
                "terrain": terrain,
                "green_ratio": round(green, 3),
                "blue_ratio": round(blue, 3),
                "gray_ratio": round(gray, 3),
            }
        except Exception:
            return {}

    def _detect_cues(self, ctx: CaseContext, scene: Dict[str, Any]) -> List[str]:
        cues: List[str] = []
        meta = ctx.prior(StageName.METADATA) or {}
        if meta.get("gps"):
            cues.append("gps")
        ocr = ctx.prior(StageName.OCR) or {}
        if ocr.get("location_clues"):
            cues.append("ocr_location_clue")
        if scene.get("tags"):
            cues.append("scene:" + ",".join(scene["tags"]))
        return cues

    def _candidates(self, ctx: CaseContext, scene: Dict[str, Any]) -> List[Dict[str, Any]]:
        candidates: List[Dict[str, Any]] = []
        meta = ctx.prior(StageName.METADATA) or {}
        gps = meta.get("gps")
        if gps:
            candidates.append(
                {
                    "country": "unknown",
                    "state": "unknown",
                    "city": "unknown",
                    "lat": gps.get("lat"),
                    "lon": gps.get("lon"),
                    "confidence": 90.0,
                    "basis": "gps",
                }
            )
        ocr = ctx.prior(StageName.OCR) or {}
        for clue in (ocr.get("location_clues") or [])[:5]:
            candidates.append(
                {"country": "unknown", "state": "unknown", "city": str(clue), "confidence": 55.0, "basis": "ocr"}
            )
        # Scene-only inference: a low-confidence terrain hint when nothing else.
        if not candidates and scene.get("terrain"):
            candidates.append(
                {
                    "country": "unknown",
                    "state": "unknown",
                    "city": f"({scene['terrain']} scene)",
                    "confidence": 20.0,
                    "basis": "scene",
                }
            )
        return candidates


__all__ = ["GeointEngine"]
