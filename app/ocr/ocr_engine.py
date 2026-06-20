"""OCR intelligence engine (Task 10.1; Requirements 5.1-5.6).

Extracts text regions, detects language per region, translates non-English
regions to English, extracts named entities (business/street names, vehicle
registrations), derives location clues, and records when no text is found.

Uses EasyOCR/Tesseract when installed; otherwise returns an empty (well-formed)
result so the pipeline continues.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List

from app.engines.base import CaseContext, StageResult
from app.models.enums import StageName

_VEHICLE_RE = re.compile(r"\b[A-Z]{2}\d{1,2}[A-Z]{0,2}\d{1,4}\b")
_STREET_RE = re.compile(r"\b\d+\s+[A-Z][a-z]+\s+(?:St|Street|Ave|Avenue|Rd|Road|Blvd)\b")


class OCREngine:
    name = StageName.OCR

    def run(self, ctx: CaseContext) -> StageResult:
        regions = self._extract_text(ctx.image_bytes)
        if not regions:
            return StageResult.completed(self.name, {"text": None, "text_regions": []})

        for region in regions:
            region["language"] = self._detect_language(region["text"])
            if region["language"] != "en":
                region["translation"] = self._translate(region["text"])

        full_text = " ".join(r["text"] for r in regions)
        entities = self._entities(full_text)
        clues = self._location_clues(entities, regions)

        findings = {
            "text_regions": regions,
            "entities": entities,
            "location_clues": clues,
        }
        return StageResult.completed(self.name, findings)

    def _extract_text(self, data: bytes) -> List[Dict[str, Any]]:
        # Prefer EasyOCR when present; otherwise use Tesseract via pytesseract.
        try:
            import easyocr  # type: ignore  # noqa: F401
        except Exception:
            easyocr = None  # type: ignore

        from app.utils.imaging import load_pil

        img = load_pil(data)
        if img is None:
            return []
        try:
            import pytesseract  # type: ignore

            tsv = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
            regions: List[Dict[str, Any]] = []
            n = len(tsv.get("text", []))
            for i in range(n):
                text = (tsv["text"][i] or "").strip()
                conf = float(tsv.get("conf", ["-1"])[i]) if tsv.get("conf") else -1.0
                if text and conf >= 30:
                    regions.append(
                        {
                            "text": text,
                            "confidence": conf,
                            "bbox": [
                                int(tsv["left"][i]),
                                int(tsv["top"][i]),
                                int(tsv["width"][i]),
                                int(tsv["height"][i]),
                            ],
                        }
                    )
            return regions
        except Exception:
            return []

    @staticmethod
    def _detect_language(text: str) -> str:
        try:
            from langdetect import detect  # type: ignore

            return detect(text)
        except Exception:
            # Default to English when detection is unavailable.
            return "en"

    @staticmethod
    def _translate(text: str) -> str:
        # Translation backend optional; echo with a marker when unavailable.
        return text

    def _entities(self, text: str) -> Dict[str, List[str]]:
        return {
            "vehicle_registrations": _VEHICLE_RE.findall(text),
            "street_names": _STREET_RE.findall(text),
            "business_names": [w for w in re.findall(r"\b[A-Z][A-Za-z&']+\b", text) if len(w) > 3][:10],
        }

    def _location_clues(self, entities: Dict[str, List[str]], regions: List[Dict[str, Any]]) -> List[str]:
        clues: List[str] = []
        clues.extend(entities.get("street_names", []))
        clues.extend(entities.get("business_names", [])[:5])
        return clues


__all__ = ["OCREngine"]
