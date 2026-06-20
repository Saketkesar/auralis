"""Unit tests for the common engine contract (Task 2.1).

Covers the transport :class:`StageResult`, :class:`ArtifactRef`,
:class:`CaseContext`, the :class:`AnalysisEngine` protocol, and the
:func:`run_engine` failure-isolation wrapper. The central guarantee under test
is that engines never raise to the orchestrator (Requirements 21.3, 21.4).
"""
from __future__ import annotations

import uuid

import pytest

from app.engines.base import (
    AnalysisEngine,
    ArtifactRef,
    CaseContext,
    StageResult,
    run_engine,
)
from app.models.enums import ArtifactKind, StageName, StageStatus


# --------------------------------------------------------------------------- #
# StageResult invariants and factories
# --------------------------------------------------------------------------- #
def test_completed_factory_sets_status_and_findings():
    result = StageResult.completed(
        StageName.METADATA, {"gps_removed": False}, score=22.5
    )
    assert result.stage is StageName.METADATA
    assert result.status is StageStatus.COMPLETED
    assert result.findings == {"gps_removed": False}
    assert result.score == 22.5
    assert result.error is None
    assert result.artifacts == []


def test_failed_factory_requires_and_records_error():
    result = StageResult.failed(StageName.OCR, "boom")
    assert result.status is StageStatus.FAILED
    assert result.error == "boom"


def test_not_applicable_factory():
    result = StageResult.not_applicable(
        StageName.DEEPFAKE, {"reason": "no faces"}
    )
    assert result.status is StageStatus.NOT_APPLICABLE
    assert result.error is None


def test_failed_status_without_error_is_rejected():
    with pytest.raises(ValueError):
        StageResult(stage=StageName.OCR, status=StageStatus.FAILED)


def test_error_set_on_non_failed_status_is_rejected():
    with pytest.raises(ValueError):
        StageResult(
            stage=StageName.OCR,
            status=StageStatus.COMPLETED,
            error="should not be here",
        )


def test_string_stage_and_status_are_coerced_to_enums():
    result = StageResult(stage="metadata", status="completed")
    assert result.stage is StageName.METADATA
    assert result.status is StageStatus.COMPLETED


def test_invalid_stage_value_raises():
    with pytest.raises(ValueError):
        StageResult(stage="not_a_stage", status=StageStatus.COMPLETED)


def test_to_orm_fields_maps_to_stage_results_columns():
    artifact = ArtifactRef(ArtifactKind.HEATMAP, "cases/x/heatmap.png", "image/png", 10)
    result = StageResult.completed(
        StageName.TAMPERING, {"k": "v"}, score=80.0, artifacts=[artifact]
    )
    fields = result.to_orm_fields()
    # Exactly the ORM column names the orchestrator persists (artifacts excluded).
    assert fields == {
        "stage": StageName.TAMPERING,
        "status": StageStatus.COMPLETED,
        "findings": {"k": "v"},
        "score": 80.0,
        "error": None,
    }


# --------------------------------------------------------------------------- #
# ArtifactRef
# --------------------------------------------------------------------------- #
def test_artifact_ref_to_orm_fields():
    ref = ArtifactRef(ArtifactKind.EXTRACTED_PAYLOAD, "cases/x/payload.bin")
    assert ref.to_orm_fields() == {
        "kind": ArtifactKind.EXTRACTED_PAYLOAD,
        "object_key": "cases/x/payload.bin",
        "mime_type": None,
        "size_bytes": None,
    }


# --------------------------------------------------------------------------- #
# CaseContext
# --------------------------------------------------------------------------- #
def test_case_context_exposes_read_only_inputs():
    cid = uuid.uuid4()
    ctx = CaseContext(
        case_id=cid,
        image_bytes=b"\xff\xd8\xff",
        prior_findings={StageName.METADATA: {"gps": {"lat": 1.0}}},
        config={"min_confidence": 30},
    )
    assert ctx.case_id == cid
    assert ctx.image_bytes == b"\xff\xd8\xff"
    assert ctx.prior(StageName.METADATA) == {"gps": {"lat": 1.0}}
    assert ctx.prior("metadata") == {"gps": {"lat": 1.0}}
    assert ctx.prior(StageName.OCR) is None
    assert ctx.get_config("min_confidence") == 30
    assert ctx.get_config("missing", "default") == "default"


def test_case_context_prior_returns_a_copy():
    ctx = CaseContext(
        case_id=uuid.uuid4(),
        image_bytes=b"x",
        prior_findings={StageName.METADATA: {"flags": {"a": 1}}},
    )
    snapshot = ctx.prior(StageName.METADATA)
    snapshot["flags"] = "mutated"
    # Mutating the returned copy must not affect the stored findings.
    assert ctx.prior(StageName.METADATA) == {"flags": {"a": 1}}


def test_case_context_config_is_read_only():
    ctx = CaseContext(case_id=uuid.uuid4(), image_bytes=b"x", config={"a": 1})
    with pytest.raises(TypeError):
        ctx.config["a"] = 2  # type: ignore[index]


# --------------------------------------------------------------------------- #
# AnalysisEngine protocol + run_engine isolation
# --------------------------------------------------------------------------- #
class _GoodEngine:
    name = StageName.METADATA

    def run(self, ctx: CaseContext) -> StageResult:
        return StageResult.completed(self.name, {"ok": True}, score=10.0)


class _RaisingEngine:
    name = StageName.OCR

    def run(self, ctx: CaseContext) -> StageResult:
        raise RuntimeError("kaboom")


class _BadReturnEngine:
    name = StageName.THREAT

    def run(self, ctx: CaseContext):
        return {"not": "a stage result"}


class _StringNameEngine:
    name = "geoint"

    def run(self, ctx: CaseContext) -> StageResult:
        raise ValueError("oops")


def _ctx() -> CaseContext:
    return CaseContext(case_id=uuid.uuid4(), image_bytes=b"img")


def test_good_engine_satisfies_protocol():
    assert isinstance(_GoodEngine(), AnalysisEngine)


def test_run_engine_passes_through_successful_result():
    result = run_engine(_GoodEngine(), _ctx())
    assert result.status is StageStatus.COMPLETED
    assert result.findings == {"ok": True}


def test_run_engine_converts_exception_to_failed_result():
    result = run_engine(_RaisingEngine(), _ctx())
    assert result.stage is StageName.OCR
    assert result.status is StageStatus.FAILED
    assert "RuntimeError" in (result.error or "")
    assert "kaboom" in (result.error or "")


def test_run_engine_rejects_non_stage_result_return():
    result = run_engine(_BadReturnEngine(), _ctx())
    assert result.stage is StageName.THREAT
    assert result.status is StageStatus.FAILED
    assert "expected StageResult" in (result.error or "")


def test_run_engine_resolves_string_engine_name_on_failure():
    result = run_engine(_StringNameEngine(), _ctx())
    assert result.stage is StageName.GEOINT
    assert result.status is StageStatus.FAILED
