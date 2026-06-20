"""Weather and shadow analysis engine (Task 15.3; Requirements 18.1-18.5).

Estimates time-of-day and weather from real image statistics: overall
brightness (day/twilight/night), a sky-region colour analysis (clear/overcast),
and a directional-gradient shadow estimate. Associates a Confidence_Score with
the estimated capture time, and records when estimation is not possible.
"""
from __future__ import annotations

from typing import Any, Dict

from app.engines.base import CaseContext, StageResult
from app.models.enums import StageName
from app.utils.imaging import cv2, has_cv2, load_array, np
from app.utils.scoring import bounded_score


class WeatherEngine:
    name = StageName.WEATHER

    def run(self, ctx: CaseContext) -> StageResult:
        cues = self._detect_cues(ctx.image_bytes)
        if not cues.get("analyzable"):
            return StageResult.completed(
                self.name,
                {"time_estimation_possible": False, "reason": "image could not be analyzed"},
            )

        confidence = bounded_score(cues.get("confidence", 40.0))
        findings = {
            "time_estimation_possible": True,
            "brightness": cues["brightness"],
            "time_of_day": cues["time_of_day"],
            "weather": cues["weather"],
            "shadow_direction": cues["shadow_direction"],
            "shadow_strength": cues["shadow_strength"],
            "capture_time_confidence": confidence,
        }
        return StageResult.completed(self.name, findings, score=confidence)

    def _detect_cues(self, data: bytes) -> Dict[str, Any]:
        arr = load_array(data)
        if arr is None or not has_cv2() or np is None:
            return {"analyzable": False}
        try:
            hsv = cv2.cvtColor(arr, cv2.COLOR_RGB2HSV)
            v = hsv[:, :, 2].astype("float32") / 255.0
            brightness = float(v.mean())
            if brightness > 0.55:
                tod = "daytime"
            elif brightness > 0.28:
                tod = "dawn/dusk"
            else:
                tod = "night"

            # Sky region = top third; high blue + low saturation => clear sky.
            top = arr[: arr.shape[0] // 3]
            b_mean = float(top[:, :, 2].mean())
            sat = float(hsv[: arr.shape[0] // 3, :, 1].mean()) / 255.0
            if brightness < 0.28:
                weather = "unknown (low light)"
            elif b_mean > 130 and sat > 0.2:
                weather = "clear"
            elif b_mean > 120 and sat <= 0.2:
                weather = "overcast/hazy"
            else:
                weather = "indeterminate"

            # Shadow direction via dominant gradient orientation on dark pixels.
            gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
            gx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
            gy = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
            mag = np.sqrt(gx**2 + gy**2)
            strength = float(min(1.0, mag.mean() / 50.0))
            ang = float(np.degrees(np.arctan2(gy.mean(), gx.mean())))
            shadow_dir = self._cardinal(ang)

            # Confidence higher when lighting is decisive.
            conf = 30.0 + abs(brightness - 0.4) * 80.0 + strength * 20.0
            return {
                "analyzable": True,
                "brightness": round(brightness, 3),
                "time_of_day": tod,
                "weather": weather,
                "shadow_direction": shadow_dir,
                "shadow_strength": round(strength, 3),
                "confidence": conf,
            }
        except Exception:
            return {"analyzable": False}

    @staticmethod
    def _cardinal(angle: float) -> str:
        dirs = ["E", "SE", "S", "SW", "W", "NW", "N", "NE"]
        idx = int(((angle + 360) % 360) / 45) % 8
        return dirs[idx]


__all__ = ["WeatherEngine"]
