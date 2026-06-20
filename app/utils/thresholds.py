"""Threshold-based alert flagging helpers.

Several engines raise an alert when a score crosses a configured threshold, but
they do not all use the same comparison. The requirements split into two cases:

* **At-or-above** alerts fire when a score *meets or exceeds* the threshold.
  Used by the AI-image engine (Requirement 13.4 -- flag likely AI-generated when
  the AI-generation probability meets the configured alert threshold) and the
  threat engine (Requirement 17.4 -- flag a potential threat when the threat
  Risk_Score meets the configured alert threshold).

* **Below** alerts fire when a score falls *strictly below* the threshold. Used
  by the deepfake engine (Requirement 14.3 -- flag likely deepfake when the
  authenticity Confidence_Score falls below the configured alert threshold).

Centralising the two comparison rules here keeps every engine consistent about
the boundary case (a score exactly equal to the threshold) and makes the rule
itself a single, testable unit.
"""
from __future__ import annotations

__all__ = ["flag_at_or_above", "flag_below"]


def flag_at_or_above(score: float, threshold: float) -> bool:
    """Return ``True`` when ``score`` meets or exceeds ``threshold``.

    This implements the "meets the configured alert threshold" rule used by the
    AI-image (13.4) and threat (17.4) alerts: a score exactly equal to the
    threshold *does* raise the flag.

    Args:
        score: The engine-produced Confidence_Score or Risk_Score.
        threshold: The configured alert threshold to compare against.

    Returns:
        ``True`` if ``score >= threshold``, otherwise ``False``.
    """
    return score >= threshold


def flag_below(score: float, threshold: float) -> bool:
    """Return ``True`` when ``score`` falls strictly below ``threshold``.

    This implements the "falls below the configured alert threshold" rule used
    by the deepfake authenticity alert (14.3): a score exactly equal to the
    threshold does *not* raise the flag.

    Args:
        score: The engine-produced Confidence_Score or Risk_Score.
        threshold: The configured alert threshold to compare against.

    Returns:
        ``True`` if ``score < threshold``, otherwise ``False``.
    """
    return score < threshold
