"""Common engine contract and case context (Task 2.1).

This module defines the single interface every analysis engine implements so the
:class:`~app.services.pipeline_orchestrator.PipelineOrchestrator` can treat all
engines uniformly. It is the backbone of *failure isolation*: an engine never
raises to the orchestrator. Instead it catches its own internal errors and
returns a :class:`StageResult` with ``status = StageStatus.FAILED`` and a
populated ``error`` message, and the orchestrator records whatever result it
receives and continues with the remaining stages (Requirements 21.3, 21.4).

Two distinct ``StageResult`` types exist in the codebase, intentionally:

* :class:`app.models.stage_result.StageResult` — the **ORM row** persisted to the
  ``stage_results`` table (one per ``(case_id, stage)``).
* :class:`app.engines.base.StageResult` (this module) — the **transport/result**
  object an engine returns to the orchestrator.

The transport object is deliberately ignorant of the database: it carries no
``case_id``, no primary key, and no relationships. :meth:`StageResult.to_orm_fields`
maps it onto the ORM column names so the orchestrator can persist it without the
engine ever importing the ORM layer.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping, Protocol, runtime_checkable

from app.models.enums import ArtifactKind, StageName, StageStatus

__all__ = [
    "ArtifactRef",
    "CaseContext",
    "StageResult",
    "AnalysisEngine",
    "run_engine",
]


@dataclass(frozen=True)
class ArtifactRef:
    """A reference to a derived artifact an engine has stored in object storage.

    Engines that produce binary outputs (tampering heatmaps, extracted stego
    payloads, carved CTF files, channel images) write the bytes to MinIO and
    return one ``ArtifactRef`` per object. The fields map directly onto the
    persisted :class:`app.models.artifact.Artifact` columns; the orchestrator
    supplies ``case_id`` and ``stage`` when it writes the row, so they are not
    carried here (Requirements 12.3, 15.2, 16.4).
    """

    kind: ArtifactKind
    object_key: str
    mime_type: str | None = None
    size_bytes: int | None = None

    def to_orm_fields(self) -> dict[str, Any]:
        """Return the artifact columns the orchestrator persists for this ref.

        The orchestrator merges ``case_id`` and ``stage`` into these fields when
        creating the :class:`~app.models.artifact.Artifact` row.
        """
        return {
            "kind": self.kind,
            "object_key": self.object_key,
            "mime_type": self.mime_type,
            "size_bytes": self.size_bytes,
        }


@dataclass
class StageResult:
    """The transport result an engine returns to the orchestrator.

    This is *not* the persisted ORM row (see module docstring). It is a plain,
    JSON-friendly value object describing the outcome of running one analysis
    stage. The orchestrator persists it verbatim via :meth:`to_orm_fields`.

    Invariants (enforced in :meth:`__post_init__`):

    * ``error`` is populated **iff** ``status == StageStatus.FAILED``.
    * ``status`` is always a :class:`~app.models.enums.StageStatus` and ``stage``
      a :class:`~app.models.enums.StageName` (strings are coerced for ergonomics).
    """

    stage: StageName
    status: StageStatus
    findings: dict[str, Any] = field(default_factory=dict)
    artifacts: list[ArtifactRef] = field(default_factory=list)
    score: float | None = None
    error: str | None = None

    def __post_init__(self) -> None:
        # Coerce the canonical-string forms (StageName/StageStatus subclass str)
        # so callers may pass either the enum member or its value.
        if not isinstance(self.stage, StageName):
            self.stage = StageName(self.stage)
        if not isinstance(self.status, StageStatus):
            self.status = StageStatus(self.status)

        if self.status is StageStatus.FAILED:
            if not self.error:
                raise ValueError(
                    "a FAILED StageResult must carry a non-empty error message"
                )
        elif self.error is not None:
            raise ValueError(
                "error may only be set when status is FAILED "
                f"(got status={self.status.value!r}, error={self.error!r})"
            )

    # -- factory constructors -------------------------------------------------
    @classmethod
    def completed(
        cls,
        stage: StageName | str,
        findings: dict[str, Any] | None = None,
        *,
        score: float | None = None,
        artifacts: list[ArtifactRef] | None = None,
    ) -> "StageResult":
        """Build a successful (``COMPLETED``) result."""
        return cls(
            stage=stage if isinstance(stage, StageName) else StageName(stage),
            status=StageStatus.COMPLETED,
            findings=findings or {},
            artifacts=list(artifacts or []),
            score=score,
        )

    @classmethod
    def failed(
        cls,
        stage: StageName | str,
        error: str,
        *,
        findings: dict[str, Any] | None = None,
    ) -> "StageResult":
        """Build a failure (``FAILED``) result with the captured error message."""
        return cls(
            stage=stage if isinstance(stage, StageName) else StageName(stage),
            status=StageStatus.FAILED,
            findings=findings or {},
            error=error,
        )

    @classmethod
    def not_applicable(
        cls,
        stage: StageName | str,
        findings: dict[str, Any] | None = None,
    ) -> "StageResult":
        """Build a ``NOT_APPLICABLE`` result (e.g. deepfake with no faces)."""
        return cls(
            stage=stage if isinstance(stage, StageName) else StageName(stage),
            status=StageStatus.NOT_APPLICABLE,
            findings=findings or {},
        )

    # -- persistence mapping --------------------------------------------------
    def to_orm_fields(self) -> dict[str, Any]:
        """Map this transport result onto ``stage_results`` column names.

        The orchestrator combines these with ``case_id`` and the
        ``started_at`` / ``completed_at`` timestamps it controls to create or
        update the :class:`app.models.stage_result.StageResult` ORM row. The
        ``artifacts`` are persisted separately as
        :class:`~app.models.artifact.Artifact` rows.
        """
        return {
            "stage": self.stage,
            "status": self.status,
            "findings": self.findings,
            "score": self.score,
            "error": self.error,
        }


class CaseContext:
    """Read-only inputs handed to an engine for a single Case run.

    Carries the case identifier, an immutable handle to the original image
    bytes, the findings produced by prior stages, and the configuration
    (thresholds, result caps, etc.) the engine needs. All accessors return
    read-only views so an engine cannot mutate shared pipeline state.
    """

    __slots__ = ("_case_id", "_image_bytes", "_prior_findings", "_config")

    def __init__(
        self,
        case_id: uuid.UUID,
        image_bytes: bytes,
        prior_findings: Mapping[StageName | str, dict[str, Any]] | None = None,
        config: Mapping[str, Any] | None = None,
    ) -> None:
        self._case_id = case_id
        # bytes are immutable; store directly as the read-only image handle.
        self._image_bytes = bytes(image_bytes)
        # Normalise prior-finding keys to canonical StageName values.
        normalised: dict[StageName, dict[str, Any]] = {}
        for key, value in (prior_findings or {}).items():
            stage = key if isinstance(key, StageName) else StageName(key)
            normalised[stage] = dict(value)
        self._prior_findings = normalised
        self._config: Mapping[str, Any] = MappingProxyType(dict(config or {}))

    @property
    def case_id(self) -> uuid.UUID:
        return self._case_id

    @property
    def image_bytes(self) -> bytes:
        """The original image bytes, unmodified (immutable)."""
        return self._image_bytes

    @property
    def config(self) -> Mapping[str, Any]:
        """Read-only configuration mapping (thresholds, caps, ...)."""
        return self._config

    def prior(self, stage: StageName | str) -> dict[str, Any] | None:
        """Return a copy of a prior stage's findings, or ``None`` if absent.

        A copy is returned so the engine cannot mutate another stage's result.
        """
        key = stage if isinstance(stage, StageName) else StageName(stage)
        found = self._prior_findings.get(key)
        return dict(found) if found is not None else None

    def get_config(self, key: str, default: Any = None) -> Any:
        """Return a single configuration value with a fallback default."""
        return self._config.get(key, default)


@runtime_checkable
class AnalysisEngine(Protocol):
    """The uniform contract every analysis engine implements.

    Engines expose a canonical ``name`` and a single :meth:`run` method that
    accepts a :class:`CaseContext` and returns a :class:`StageResult`. Engines
    **must not** raise to the caller: internal errors are caught and returned as
    a ``FAILED`` :class:`StageResult` (Requirement 21.3). Use :func:`run_engine`
    to obtain that guarantee even for engines that contain bugs.
    """

    name: str

    def run(self, ctx: CaseContext) -> StageResult:
        """Execute the stage against ``ctx`` and return its result."""
        ...


def run_engine(engine: AnalysisEngine, ctx: CaseContext) -> StageResult:
    """Run ``engine`` and guarantee a :class:`StageResult` is returned.

    This is the orchestrator-side safety net enforcing "engines never raise to
    the caller" (Requirement 21.3). Even if an engine forgets to catch an
    internal error, this wrapper converts the exception into a ``FAILED``
    :class:`StageResult` so the pipeline records the failure and continues with
    the remaining stages (Requirement 21.4).

    The engine's declared ``name`` is mapped to its canonical
    :class:`~app.models.enums.StageName`; if it does not match a known stage,
    the failure is still reported, defensively keyed to the raw name.
    """
    try:
        result = engine.run(ctx)
    except Exception as exc:  # noqa: BLE001 - deliberate catch-all for isolation
        return StageResult.failed(
            _stage_for(engine),
            error=f"{type(exc).__name__}: {exc}",
        )

    if not isinstance(result, StageResult):
        return StageResult.failed(
            _stage_for(engine),
            error=(
                "engine.run returned "
                f"{type(result).__name__}, expected StageResult"
            ),
        )
    return result


def _stage_for(engine: AnalysisEngine) -> StageName:
    """Resolve an engine's ``name`` to a canonical :class:`StageName`.

    A :class:`StageResult` cannot exist without a valid ``StageName``, so an
    engine whose ``name`` does not map to a known stage is a contract violation
    (developer error, not a runtime data condition) and is surfaced as a
    ``ValueError`` rather than silently mislabelled.
    """
    name = getattr(engine, "name", None)
    if isinstance(name, StageName):
        return name
    try:
        return StageName(name)
    except (ValueError, TypeError):
        # Unknown engine name: surface it via the error message but still need a
        # valid StageName for the row. Re-raise as a clear contract violation.
        raise ValueError(
            f"engine {engine!r} has an unrecognised stage name {name!r}; "
            "engine.name must be a StageName or its string value"
        )
