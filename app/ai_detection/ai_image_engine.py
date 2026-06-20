"""AI-generated image detection engine (Task 13.2; Requirements 13.1-13.4).

Combines (1) generative-model metadata signatures, (2) a frequency-domain
artifact heuristic (diffusion/GAN images tend to have atypical high-frequency
energy and periodic spectral peaks), and (3) channel-statistics smoothness, into
an AI-generation probability. Records the suspected generator family and flags
the case when the probability meets the configured threshold.
"""
from __future__ import annotations

from typing import Optional

from app.engines.base import CaseContext, StageResult
from app.models.enums import StageName
from app.utils.imaging import cv2, has_cv2, load_gray, np
from app.utils.scoring import bounded_score
from app.utils.thresholds import flag_at_or_above

_GENERATOR_SIGNATURES = {
    b"Midjourney": "midjourney",
    b"Stable Diffusion": "stable_diffusion",
    b"stable-diffusion": "stable_diffusion",
    b"Automatic1111": "stable_diffusion",
    b"DALL": "dalle",
    b"Firefly": "firefly",
    b"Adobe Firefly": "firefly",
    b"Ideogram": "ideogram",
    b"flux": "flux",
    b"C2PA": "c2pa_provenance",
}


class AIImageEngine:
    name = StageName.AI_IMAGE

    def run(self, ctx: CaseContext) -> StageResult:
        threshold = float(ctx.get_config("AI_IMAGE_ALERT_THRESHOLD", 70.0))
        family = self._signature(ctx.image_bytes)
        artifact_score, details = self._artifact_probability(ctx.image_bytes)
        probability = bounded_score(95.0 if family else artifact_score)
        flagged = flag_at_or_above(probability, threshold)
        findings = {
            "ai_probability": probability,
            "suspected_generator": family,
            "signals": details,
            "is_ai_generated": flagged,
        }
        return StageResult.completed(self.name, findings, score=probability)

    def _signature(self, data: bytes) -> Optional[str]:
        window = data[:16384] + data[-16384:]
        for sig, family in _GENERATOR_SIGNATURES.items():
            if sig in window:
                return family
        return None

    def _artifact_probability(self, data: bytes):
        gray = load_gray(data)
        if gray is None or not has_cv2() or np is None:
            return 10.0, {"method": "unavailable"}
        try:
            g = gray.astype("float32") / 255.0
            f = np.fft.fftshift(np.fft.fft2(g))
            mag = np.log1p(np.abs(f))
            h, w = mag.shape
            cy, cx = h // 2, w // 2
            r = max(4, min(h, w) // 8)
            # Ratio of high-frequency energy to total energy.
            total = float(mag.sum()) or 1.0
            low = float(mag[cy - r : cy + r, cx - r : cx + r].sum())
            high_ratio = 1.0 - (low / total)
            # Residual/noise flatness via Laplacian (AI images often very smooth).
            lap_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
            smoothness = max(0.0, 1.0 - min(1.0, lap_var / 500.0))
            score = bounded_score(high_ratio * 60.0 + smoothness * 40.0)
            return score, {
                "method": "fft+laplacian",
                "high_freq_ratio": round(high_ratio, 4),
                "laplacian_variance": round(lap_var, 2),
            }
        except Exception:
            return 10.0, {"method": "error"}


__all__ = ["AIImageEngine"]
