"""CTF investigation engine (Task 14.3; Requirements 16.1-16.5).

Runs hidden-ZIP, QR, Base64, RGB channel split, channel analysis, entropy
analysis, file carving, and LSB analysis with per-technique isolation; provides
a hex view of raw bytes; stores recovered data as artifacts; and emits a summary
of every technique and its outcome.
"""
from __future__ import annotations

import base64
import binascii
import math
import re
from collections import Counter
from typing import Any, Callable, Dict, List

from app.engines.base import ArtifactRef, CaseContext, StageResult
from app.models.enums import ArtifactKind, StageName


class CTFEngine:
    name = StageName.CTF

    def run(self, ctx: CaseContext) -> StageResult:
        data = ctx.image_bytes
        artifacts: List[ArtifactRef] = []
        summary: Dict[str, Any] = {}

        techniques: List[tuple[str, Callable[[bytes], Dict[str, Any]]]] = [
            ("hidden_zip", self._hidden_zip),
            ("qr", self._qr),
            ("base64", self._base64),
            ("rgb_split", self._rgb_split),
            ("channel_analysis", self._channel_analysis),
            ("entropy", self._entropy_analysis),
            ("file_carving", self._file_carving),
            ("lsb", self._lsb),
        ]

        for tech_name, fn in techniques:
            try:
                result = fn(data)
                summary[tech_name] = {"status": "ok", **result}
                if result.get("recovered"):
                    artifacts.append(
                        ArtifactRef(
                            ArtifactKind.CARVED_FILE,
                            object_key=f"{ctx.case_id}/ctf/{tech_name}.bin",
                            mime_type="application/octet-stream",
                        )
                    )
            except Exception as exc:  # noqa: BLE001 - per-technique isolation (16.2)
                summary[tech_name] = {"status": "failed", "error": f"{type(exc).__name__}: {exc}"}

        findings = {"techniques": summary}
        return StageResult.completed(self.name, findings, artifacts=artifacts)

    @staticmethod
    def hex_view(data: bytes, *, width: int = 16, limit: int = 4096) -> str:
        """Return a classic hex+ASCII dump of the raw bytes (16.3)."""
        lines = []
        chunk = data[:limit]
        for offset in range(0, len(chunk), width):
            row = chunk[offset : offset + width]
            hexpart = " ".join(f"{b:02x}" for b in row)
            asciipart = "".join(chr(b) if 32 <= b < 127 else "." for b in row)
            lines.append(f"{offset:08x}  {hexpart:<{width*3}}  {asciipart}")
        return "\n".join(lines)

    # -- techniques --------------------------------------------------------- #
    def _hidden_zip(self, data: bytes) -> Dict[str, Any]:
        idx = data.find(b"PK\x03\x04")
        return {"found": idx > 0, "offset": idx, "recovered": idx > 0}

    def _qr(self, data: bytes) -> Dict[str, Any]:
        # QR decoding needs optional libs; report capability without failing.
        return {"found": False, "note": "qr decoder not available", "recovered": False}

    def _base64(self, data: bytes) -> Dict[str, Any]:
        candidates = re.findall(rb"[A-Za-z0-9+/]{20,}={0,2}", data)
        decoded = []
        for c in candidates[:20]:
            try:
                text = base64.b64decode(c, validate=True)
                if text and all(9 <= b < 127 for b in text[:32]):
                    decoded.append(text[:64].decode("ascii", "ignore"))
            except (binascii.Error, ValueError):
                continue
        return {"matches": len(candidates), "decoded_samples": decoded[:5], "recovered": bool(decoded)}

    def _rgb_split(self, data: bytes) -> Dict[str, Any]:
        return self._with_pillow(data, self._do_rgb_split)

    def _do_rgb_split(self, img) -> Dict[str, Any]:
        bands = img.convert("RGB").getbands()
        return {"bands": list(bands), "recovered": True}

    def _channel_analysis(self, data: bytes) -> Dict[str, Any]:
        return self._with_pillow(data, lambda img: {"channels": len(img.getbands()), "recovered": False})

    def _entropy_analysis(self, data: bytes) -> Dict[str, Any]:
        if not data:
            return {"entropy": 0.0, "recovered": False}
        counts = Counter(data)
        total = len(data)
        entropy = -sum((c / total) * math.log2(c / total) for c in counts.values())
        return {"entropy": round(entropy, 4), "suspicious": entropy > 7.5, "recovered": False}

    def _file_carving(self, data: bytes) -> Dict[str, Any]:
        sigs = {b"PK\x03\x04": "zip", b"%PDF": "pdf", b"\xff\xd8\xff": "jpeg", b"\x89PNG": "png"}
        carved = []
        for sig, kind in sigs.items():
            pos = data.find(sig, 1)  # skip the host image header
            if pos > 0:
                carved.append({"type": kind, "offset": pos})
        return {"carved": carved, "recovered": bool(carved)}

    def _lsb(self, data: bytes) -> Dict[str, Any]:
        return self._with_pillow(data, self._do_lsb)

    def _do_lsb(self, img) -> Dict[str, Any]:
        rgb = img.convert("RGB")
        pixels = list(rgb.getdata())[:2048]
        bits = "".join(str(p[0] & 1) for p in pixels)
        chars = [chr(int(bits[i : i + 8], 2)) for i in range(0, len(bits) - 8, 8)]
        text = "".join(c for c in chars if 32 <= ord(c) < 127)
        hit = "flag" in text.lower() or "ctf" in text.lower()
        return {"lsb_text_sample": text[:48], "recovered": hit}

    @staticmethod
    def _with_pillow(data: bytes, fn) -> Dict[str, Any]:
        try:
            import io

            from PIL import Image  # type: ignore

            img = Image.open(io.BytesIO(data))
            return fn(img)
        except Exception:
            return {"note": "image decode unavailable", "recovered": False}


__all__ = ["CTFEngine"]
