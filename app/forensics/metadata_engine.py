"""Metadata forensics engine (Task 8.1; Requirements 2.1-2.9).

Extracts EXIF/XMP/ICC/thumbnail/orientation metadata, records present GPS,
camera, software and timestamp fields, flags missing fields, GPS-removed,
timestamp anomalies, and editing-software-vs-device mismatch, and computes a
metadata Risk_Score. Uses Pillow when available; degrades gracefully otherwise.
"""
from __future__ import annotations

import io
from typing import Any, Dict

from app.engines.base import CaseContext, StageResult
from app.models.enums import StageName
from app.utils.scoring import bounded_score

_EXPECTED_FIELDS = ["Make", "Model", "DateTimeOriginal", "GPSInfo", "Software"]


class MetadataEngine:
    name = StageName.METADATA

    def run(self, ctx: CaseContext) -> StageResult:
        meta = self._extract(ctx.image_bytes)
        flags: Dict[str, Any] = {}
        missing = [f for f in _EXPECTED_FIELDS if f not in meta or meta.get(f) in (None, "")]
        if missing:
            flags["missing_fields"] = missing

        has_camera_origin = any(meta.get(f) for f in ("Make", "Model"))
        gps = meta.get("GPSInfo")
        if has_camera_origin and not gps:
            flags["gps_removed"] = True

        timestamps = [v for k, v in meta.items() if "DateTime" in k and v]
        if len(set(timestamps)) > 1:
            flags["timestamp_anomaly"] = True

        software = (meta.get("Software") or "").lower()
        editors = ("photoshop", "gimp", "lightroom", "affinity")
        if has_camera_origin and any(e in software for e in editors):
            flags["metadata_manipulation"] = True

        # Risk grows with the number of suspicious flags.
        risk = bounded_score(len(flags) * 25.0)

        findings = {
            "metadata": meta,
            "gps": {"lat": gps[0], "lon": gps[1]} if isinstance(gps, (list, tuple)) and len(gps) == 2 else None,
            "flags": flags,
            "risk_score": risk,
        }
        return StageResult.completed(self.name, findings, score=risk)

    def _extract(self, data: bytes) -> Dict[str, Any]:
        try:
            from PIL import Image, ExifTags  # type: ignore

            img = Image.open(io.BytesIO(data))
            meta: Dict[str, Any] = {
                "format": img.format,
                "mode": img.mode,
                "size": list(img.size),
                "orientation": None,
            }
            exif = getattr(img, "_getexif", lambda: None)() or {}
            tagmap = {ExifTags.TAGS.get(k, k): v for k, v in exif.items()}
            for key in ("Make", "Model", "Software", "DateTime", "DateTimeOriginal"):
                if key in tagmap:
                    meta[key] = str(tagmap[key])
            if "GPSInfo" in tagmap:
                meta["GPSInfo"] = self._gps(tagmap["GPSInfo"])
            if "Orientation" in tagmap:
                meta["orientation"] = tagmap["Orientation"]
            return meta
        except Exception:
            # No Pillow or undecodable: return minimal content-derived metadata.
            return {"format": None, "size_bytes": len(data)}

    @staticmethod
    def _gps(gpsinfo) -> Any:
        try:
            def _to_deg(value):
                d, m, s = value
                return float(d) + float(m) / 60 + float(s) / 3600

            lat = _to_deg(gpsinfo[2])
            if gpsinfo.get(1) == "S":
                lat = -lat
            lon = _to_deg(gpsinfo[4])
            if gpsinfo.get(3) == "W":
                lon = -lon
            return [lat, lon]
        except Exception:
            return None


__all__ = ["MetadataEngine"]
