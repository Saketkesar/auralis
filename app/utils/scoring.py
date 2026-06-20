"""Bounded scoring utility.

Most AURALIS VISION engines emit a ``Confidence_Score`` or ``Risk_Score`` that
the requirements define as a numeric value in the closed interval ``[0, 100]``
(see the Glossary plus Requirements 2.5, 3.3, 4.3, 8.5, 9.3, 12.4, 13.2, 14.2,
15.3, 17.2, 18.4). Rather than re-implementing clamping in every engine, all
scoring producers funnel their raw value through :func:`bounded_score` so the
invariant is guaranteed in exactly one place.

The function is deliberately total: every input maps to a value in ``[0, 100]``.
Out-of-range numbers are clamped to the nearest bound and non-finite inputs are
resolved sensibly (``NaN`` -> ``default``, ``+inf`` -> ``100``, ``-inf`` -> ``0``)
so a misbehaving model can never poison a Case score with an invalid value.
"""
from __future__ import annotations

import math
from numbers import Real

__all__ = ["SCORE_MIN", "SCORE_MAX", "bounded_score"]

# The inclusive bounds every Confidence_Score / Risk_Score must satisfy.
SCORE_MIN: float = 0.0
SCORE_MAX: float = 100.0


def bounded_score(value: object, *, default: float = SCORE_MIN) -> float:
    """Coerce ``value`` into a score within the closed interval ``[0, 100]``.

    Args:
        value: The raw score produced by an engine. Any real number is accepted.
            ``bool`` is intentionally rejected because a boolean is almost never
            an intended score and silently treating ``True`` as ``1.0`` would
            mask a caller bug.
        default: The value used when ``value`` is ``None`` or ``NaN``. It is
            itself clamped into range, so callers cannot widen the bounds by
            supplying an out-of-range default.

    Returns:
        A ``float`` ``s`` such that ``SCORE_MIN <= s <= SCORE_MAX``.

    Raises:
        TypeError: If ``value`` (when not ``None``) or ``default`` is not a real
            number.

    Resolution rules:
        * ``None``            -> the (clamped) ``default``
        * ``NaN``             -> the (clamped) ``default``
        * ``+inf``            -> ``SCORE_MAX`` (100)
        * ``-inf``            -> ``SCORE_MIN`` (0)
        * ``value < 0``       -> ``SCORE_MIN`` (0)
        * ``value > 100``     -> ``SCORE_MAX`` (100)
        * otherwise           -> ``float(value)``
    """
    clamped_default = _clamp_finite(_as_score_float(default, role="default"))

    if value is None:
        return clamped_default

    numeric = _as_score_float(value, role="value")

    if math.isnan(numeric):
        return clamped_default
    if math.isinf(numeric):
        return SCORE_MAX if numeric > 0 else SCORE_MIN

    return _clamp_finite(numeric)


def _as_score_float(value: object, *, role: str) -> float:
    """Validate and convert a candidate score to ``float``.

    Rejects booleans and non-real types with a clear error rather than silently
    coercing them, which would hide bugs in the calling engine.
    """
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(
            f"score {role} must be a real number, got {type(value).__name__}"
        )
    return float(value)


def _clamp_finite(value: float) -> float:
    """Clamp a finite float into ``[SCORE_MIN, SCORE_MAX]``."""
    if value < SCORE_MIN:
        return SCORE_MIN
    if value > SCORE_MAX:
        return SCORE_MAX
    return value
