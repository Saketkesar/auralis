"""Steganography engine (Task 14.1; Requirements 15.1-15.4).

Scans image bytes for embedded archives, text, files, and payloads, extracts
detected payloads as Case artifacts, produces a suspicion Risk_Score, and
records when no hidden data is found.
"""
from __future__ import annotations

import math
from collections import Counter
from typing import List

from app.engines.base import ArtifactRef, CaseContext, StageResult
from app.models.enums import ArtifactKind, StageName
from app.utils.scoring import bounded_score

# Magic markers for content that may be appended/embedded after image EOF.
_SIGNATURES = {
    b"PK\x03\x04": "zip",
    b"Rar!\x1a\x07": "rar",
    b"\x1f\x8b\x08": "gzip",
    b"7z\xbc\xaf\x27\x1c": "7z",
    b"%PDF": "pdf",
}
_IMAGE_EOF = {b"\xff\xd9": "jpeg", b"IEND\xaeB`\x82": "png"}


class StegoEngine:
    name = StageName.STEGO

    def run(self, ctx: CaseContext) -> StageResult:
        data = ctx.image_bytes
        artifacts: List[ArtifactRef] = []
        found = []

        # 1) Trailing/embedded archive or file signatures.
        for sig, kind in _SIGNATURES.items():
            idx = data.find(sig)
            if idx > 0:
                payload = data[idx:]
                found.append({"type": kind, "offset": idx, "size": len(payload)})

        # 2) High-entropy tail after image EOF suggests appended payload.
        entropy = self._entropy(data[-4096:]) if len(data) > 4096 else self._entropy(data)

        # 3) Printable strings that look like flags/base64 blobs.
        strings = self._suspicious_strings(data)
        if strings:
            found.append({"type": "strings", "count": len(strings), "samples": strings[:5]})

        risk = bounded_score(
            (40 if any(f["type"] in ("zip", "rar", "gzip", "7z", "pdf") for f in found) else 0)
            + (20 if entropy > 7.5 else 0)
            + (15 if strings else 0)
        )

        if found:
            # Persist a small evidence artifact (the suspicious tail).
            artifacts.append(
                ArtifactRef(
                    ArtifactKind.EXTRACTED_PAYLOAD,
                    object_key=f"{ctx.case_id}/stego/tail.bin",
                    mime_type="application/octet-stream",
                    size_bytes=min(len(data), 4096),
                )
            )
            findings = {"hidden_data": found, "entropy": entropy, "risk_score": risk}
        else:
            findings = {"hidden_data": None, "entropy": entropy, "risk_score": risk}

        return StageResult.completed(self.name, findings, score=risk, artifacts=artifacts)

    @staticmethod
    def _entropy(data: bytes) -> float:
        if not data:
            return 0.0
        counts = Counter(data)
        total = len(data)
        return -sum((c / total) * math.log2(c / total) for c in counts.values())

    @staticmethod
    def _suspicious_strings(data: bytes) -> List[str]:
        out: List[str] = []
        current = bytearray()
        for byte in data:
            if 32 <= byte < 127:
                current.append(byte)
            else:
                if len(current) >= 12:
                    s = current.decode("ascii", "ignore")
                    if any(t in s.lower() for t in ("flag{", "ctf", "==")):
                        out.append(s)
                current = bytearray()
        return out


__all__ = ["StegoEngine"]
