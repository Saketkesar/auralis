"""Face analysis engine (Task 12.3; Requirements 11.1-11.5).

Detects faces (OpenCV Haar cascade), records the count, clusters visually
similar faces by colour histogram correlation, stores only non-identity
attributes (bbox, cluster id, quality), and records a count of zero when none
are detected.
"""
from __future__ import annotations

from typing import Any, Dict, List

from app.engines.base import CaseContext, StageResult
from app.models.enums import StageName
from app.utils.imaging import cv2, has_cv2, load_array, load_gray, np


class FaceEngine:
    name = StageName.FACE

    def run(self, ctx: CaseContext) -> StageResult:
        faces = self._detect(ctx.image_bytes)
        if not faces:
            return StageResult.completed(self.name, {"face_count": 0, "faces": [], "clusters": []})

        clusters = self._cluster(faces)
        safe_faces = [
            {"bbox": f["bbox"], "cluster": f["cluster"], "quality": f.get("quality")}
            for f in faces
        ]
        findings = {"face_count": len(faces), "faces": safe_faces, "clusters": clusters}
        return StageResult.completed(self.name, findings)

    def _detect(self, data: bytes) -> List[Dict[str, Any]]:
        if not has_cv2():
            return []
        gray = load_gray(data)
        arr = load_array(data)
        if gray is None or arr is None:
            return []
        try:
            clf = cv2.CascadeClassifier(
                cv2.data.haarcascades + "haarcascade_frontalface_default.xml"  # type: ignore[attr-defined]
            )
            if clf.empty():
                return []
            rects = clf.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
        except Exception:
            return []

        faces: List[Dict[str, Any]] = []
        for (x, y, w, h) in rects:
            crop = arr[y : y + h, x : x + w]
            faces.append(
                {
                    "bbox": [int(x), int(y), int(w), int(h)],
                    "quality": float(round(min(1.0, (w * h) / (gray.shape[0] * gray.shape[1]) * 8), 3)),
                    "_hist": self._hist(crop),
                    "cluster": None,
                }
            )
        return faces

    def _hist(self, crop):
        if not has_cv2() or crop is None or crop.size == 0:
            return None
        try:
            hsv = cv2.cvtColor(crop, cv2.COLOR_RGB2HSV)
            hist = cv2.calcHist([hsv], [0, 1], None, [16, 16], [0, 180, 0, 256])
            cv2.normalize(hist, hist)
            return hist
        except Exception:
            return None

    def _cluster(self, faces: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Group faces whose colour histograms correlate above a threshold."""
        next_cluster = 0
        reps: List[Any] = []
        for f in faces:
            assigned = None
            for cid, rep in enumerate(reps):
                if f["_hist"] is not None and rep is not None and has_cv2():
                    try:
                        score = cv2.compareHist(f["_hist"], rep, cv2.HISTCMP_CORREL)
                    except Exception:
                        score = 0.0
                    if score > 0.6:
                        assigned = cid
                        break
            if assigned is None:
                assigned = next_cluster
                reps.append(f["_hist"])
                next_cluster += 1
            f["cluster"] = assigned
            f.pop("_hist", None)

        groups: Dict[int, List[int]] = {}
        for idx, f in enumerate(faces):
            groups.setdefault(f["cluster"], []).append(idx)
        return [{"cluster": cid, "members": members} for cid, members in groups.items()]


__all__ = ["FaceEngine"]
