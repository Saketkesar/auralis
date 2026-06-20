"""Analysis engines package.

Each analysis engine (metadata, GEOINT, landmark, OCR, object, face, tampering,
AI-image, deepfake, stego, threat, weather, CTF) is an independently importable
module implementing the common engine contract. Engines are added here without
modifying existing ones.
"""
from app.engines.base import (
    AnalysisEngine,
    ArtifactRef,
    CaseContext,
    StageResult,
    run_engine,
)

__all__ = [
    "AnalysisEngine",
    "ArtifactRef",
    "CaseContext",
    "StageResult",
    "run_engine",
]
