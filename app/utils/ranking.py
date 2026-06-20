"""Ranking and capping utility for scored candidate lists.

Several engines emit a list of scored candidates that must be presented to the
Analyst ranked by score and capped to a configured maximum:

- GEOINT candidate locations ranked descending by Confidence_Score
  (Requirement 3.4).
- Landmark matches: at most the top 20 ranked by Confidence_Score
  (Requirement 4.2).
- AI Search Agent candidate locations: at most the top 20 ranked by
  Confidence_Score (Requirements 8.4).
- Map Correlation candidate locations ranked descending by location
  Confidence_Score (Requirement 9.4).

``rank_and_cap`` is the single implementation behind all of these. It is a pure
function with two guarantees the requirements depend on:

1. **Input-only output** — every returned element is an element of the input;
   nothing is fabricated, mutated, or duplicated. The result is always a prefix
   of the fully sorted input.
2. **Non-increasing order, capped** — results are ordered so each score is
   greater than or equal to the next, and the list is truncated to the
   configured ``limit``.

Ties (equal scores) preserve the relative order of the input because the sort is
stable, so the function is deterministic for a given input.
"""
from __future__ import annotations

from typing import Callable, Iterable, Optional, TypeVar

T = TypeVar("T")

# Candidates whose score is ``None`` (e.g. a ``NormalizedResult`` with no score)
# sort to the end, below every numeric score.
_MISSING_SCORE_RANK = float("-inf")


def _attr_or_item_score(element: object) -> Optional[float]:
    """Default score extractor.

    Reads a ``score`` attribute, then a ``confidence`` attribute, then a
    ``"score"``/``"confidence"`` mapping key. Returns ``None`` when no score is
    present so the element ranks last rather than raising.
    """
    for attr in ("score", "confidence"):
        value = getattr(element, attr, None)
        if value is not None:
            return float(value)
    if isinstance(element, dict):
        for key in ("score", "confidence"):
            value = element.get(key)
            if value is not None:
                return float(value)
    return None


def rank_and_cap(
    candidates: Iterable[T],
    limit: Optional[int],
    *,
    key: Callable[[T], Optional[float]] = _attr_or_item_score,
) -> list[T]:
    """Return ``candidates`` sorted non-increasing by score, capped to ``limit``.

    Args:
        candidates: The candidate elements to rank. Consumed once if a generator.
        limit: Maximum number of elements to return. ``None`` means no cap.
            Must be non-negative; a ``limit`` of ``0`` yields an empty list,
            satisfying "at most the top N" when ``N`` is configured to zero.
        key: Extracts a candidate's numeric score. Defaults to reading a
            ``score``/``confidence`` attribute or mapping key. A score of
            ``None`` ranks the element below all scored elements.

    Returns:
        A new list containing only elements drawn from ``candidates``, ordered so
        that each element's score is greater than or equal to the next, truncated
        to ``limit`` elements. The input is never mutated.

    Raises:
        ValueError: If ``limit`` is negative.
    """
    if limit is not None and limit < 0:
        raise ValueError(f"limit must be non-negative, got {limit}")

    materialized = list(candidates)

    def sort_key(element: T) -> float:
        score = key(element)
        return _MISSING_SCORE_RANK if score is None else float(score)

    # ``sorted`` is stable, and ``reverse=True`` preserves the input order of
    # equal-scored elements, so ranking is deterministic.
    ranked = sorted(materialized, key=sort_key, reverse=True)

    if limit is None:
        return ranked
    return ranked[:limit]
