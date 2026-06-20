"""Investigation pipeline orchestrator (Task 7.1; Requirements 21.1-21.5).

On Case creation the orchestrator runs the thirteen automatic analysis stages.
Each stage runs under the engine contract (:func:`run_engine`) so a single stage
failure is recorded and never aborts the others. Stage status/results are
persisted per stage, and once all stages reach a terminal state the case is
marked complete and the knowledge graph is assembled.

In production the stages fan out across Celery CPU/GPU queues; this module also
provides a synchronous ``run_pipeline`` used by the Celery task wrapper and by
tests, so the same orchestration logic runs in both settings.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Dict, List

from app.engines.base import AnalysisEngine, CaseContext, StageResult, run_engine
from app.models.enums import CaseStatus, StageName, StageStatus

# The thirteen automatic stages (Requirement 21.1), in dependency-aware order.
# object -> face -> deepfake; metadata -> geoint -> (landmark, reverse, map).
from app.ai_detection.ai_image_engine import AIImageEngine
from app.deepfake.deepfake_engine import DeepfakeEngine
from app.deepfake.face_engine import FaceEngine
from app.forensics.metadata_engine import MetadataEngine
from app.forensics.object_engine import ObjectEngine
from app.forensics.stego_engine import StegoEngine
from app.forensics.tampering_engine import TamperingEngine
from app.forensics.threat_engine import ThreatEngine
from app.forensics.weather_engine import WeatherEngine
from app.geoint.geoint_engine import GeointEngine
from app.geoint.landmark_engine import LandmarkEngine
from app.geoint.reverse_search_engine import ReverseSearchEngine
from app.ocr.ocr_engine import OCREngine


def _automatic_engines() -> List[AnalysisEngine]:
    """Return the automatic-stage engines in execution order.

    Ordered so stages that consume prior findings run after their producers
    (metadata -> ocr -> geoint -> landmark/reverse; object -> face -> deepfake;
    threat after ocr).
    """
    return [
        MetadataEngine(),
        OCREngine(),
        ObjectEngine(),
        FaceEngine(),
        GeointEngine(),
        LandmarkEngine(),
        ReverseSearchEngine(),
        TamperingEngine(),
        AIImageEngine(),
        DeepfakeEngine(),
        StegoEngine(),
        ThreatEngine(),
        WeatherEngine(),
    ]


class PipelineOrchestrator:
    def __init__(self, session=None, config: Dict | None = None, storage=None) -> None:
        self._session = session
        self._config = config or {}
        self._storage = storage

    def run_pipeline(self, case_id: uuid.UUID, image_bytes: bytes | None = None) -> Dict[str, str]:
        """Run all automatic stages for a Case and return per-stage statuses."""
        image_bytes = image_bytes if image_bytes is not None else self._load_image(case_id)
        prior: Dict[StageName, dict] = {}
        statuses: Dict[str, str] = {}

        self._set_case_status(case_id, CaseStatus.RUNNING)

        for engine in _automatic_engines():
            ctx = CaseContext(
                case_id=case_id,
                image_bytes=image_bytes or b"",
                prior_findings=prior,
                config=self._config,
            )
            result: StageResult = run_engine(engine, ctx)
            self._persist_stage(case_id, result)
            if result.status in (StageStatus.COMPLETED, StageStatus.NOT_APPLICABLE):
                prior[result.stage] = result.findings
            statuses[result.stage.value] = result.status.value

        # All stages terminal -> mark complete and build the knowledge graph.
        self._set_case_status(case_id, CaseStatus.COMPLETE)
        try:
            from app.services.knowledge_graph_service import build_knowledge_graph

            build_knowledge_graph(case_id, prior, session=self._session)
        except Exception:
            pass

        # Index findings after persistence; an indexing failure must not roll
        # back the persisted case (Requirement 26.3).
        try:
            from app.services.search_index import get_index

            owner_id = self._owner_id(case_id)
            flat = {k.value if hasattr(k, "value") else str(k): v for k, v in prior.items()}
            indexed = get_index(self._config or None).index_case(case_id, owner_id, flat)
            statuses["_indexed"] = "true" if indexed else "false"
        except Exception:
            statuses["_indexed"] = "false"
        return statuses

    def _owner_id(self, case_id: uuid.UUID):
        if self._session is None:
            return None
        from app.models.case import Case

        case = self._session.get(Case, case_id)
        return case.owner_id if case else None

    # -- persistence helpers ------------------------------------------------ #
    def _load_image(self, case_id: uuid.UUID) -> bytes:
        if self._storage is None:
            from app.services.storage import get_storage

            self._storage = get_storage(self._config or None)
        try:
            return self._storage.get(f"{case_id}/original")
        except Exception:
            return b""

    def _persist_stage(self, case_id: uuid.UUID, result: StageResult) -> None:
        if self._session is None:
            return
        from app.models.stage_result import StageResult as StageRow

        row = (
            self._session.query(StageRow)
            .filter(StageRow.case_id == case_id, StageRow.stage == result.stage)
            .one_or_none()
        )
        fields = result.to_orm_fields()
        now = datetime.now(timezone.utc)
        if row is None:
            row = StageRow(case_id=case_id, started_at=now, completed_at=now, **fields)
            self._session.add(row)
        else:
            for k, v in fields.items():
                setattr(row, k, v)
            row.completed_at = now
        self._session.commit()

        # Persist artifact rows (heatmaps, extracted payloads, carved files).
        if result.artifacts:
            from app.models.artifact import Artifact

            for ref in result.artifacts:
                try:
                    self._session.add(
                        Artifact(case_id=case_id, stage=result.stage, **ref.to_orm_fields())
                    )
                except Exception:
                    continue
            self._session.commit()

    def _set_case_status(self, case_id: uuid.UUID, status: CaseStatus) -> None:
        if self._session is None:
            return
        from app.models.case import Case

        case = self._session.get(Case, case_id)
        if case is not None:
            case.status = status
            self._session.commit()


__all__ = ["PipelineOrchestrator", "_automatic_engines"]
