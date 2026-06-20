"""Property-based tests for the threshold-flag utility (Task 2.7).

Property 3: Threshold flags follow the comparison rule.

The two alert-raising rules centralised in ``app.utils.thresholds`` must obey a
single, well-defined boundary convention across arbitrary score/threshold pairs:

* ``flag_at_or_above(score, threshold)`` is ``True`` iff ``score >= threshold``
  (boundary inclusive) -- used by the AI-image (13.4) and threat (17.4) alerts.
* ``flag_below(score, threshold)`` is ``True`` iff ``score < threshold``
  (boundary exclusive) -- used by the deepfake authenticity alert (14.3).
* The two rules are complementary at the same boundary: for any pair exactly one
  of them holds.

**Validates: Requirements 13.4, 14.3, 17.4**
"""
from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from app.utils.thresholds import flag_at_or_above, flag_below

# Scores and thresholds are Confidence_Score / Risk_Score values in [0, 100],
# but the comparison rule must hold for arbitrary finite values, so generate a
# broad finite range (no NaN/inf, which are not meaningful scores).
finite_floats = st.floats(
    allow_nan=False, allow_infinity=False, min_value=-1e9, max_value=1e9
)


# Feature: auralis-vision, Property 3: Threshold flags follow the comparison rule
@settings(max_examples=200)
@given(score=finite_floats, threshold=finite_floats)
def test_flag_at_or_above_matches_ge(score: float, threshold: float) -> None:
    """flag_at_or_above is True iff score >= threshold (boundary inclusive)."""
    assert flag_at_or_above(score, threshold) is (score >= threshold)


# Feature: auralis-vision, Property 3: Threshold flags follow the comparison rule
@settings(max_examples=200)
@given(score=finite_floats, threshold=finite_floats)
def test_flag_below_matches_lt(score: float, threshold: float) -> None:
    """flag_below is True iff score < threshold (boundary exclusive)."""
    assert flag_below(score, threshold) is (score < threshold)


# Feature: auralis-vision, Property 3: Threshold flags follow the comparison rule
@settings(max_examples=200)
@given(score=finite_floats, threshold=finite_floats)
def test_flags_are_complementary_at_same_boundary(
    score: float, threshold: float
) -> None:
    """Exactly one of the two rules holds for any score/threshold pair."""
    assert flag_at_or_above(score, threshold) != flag_below(score, threshold)


# Feature: auralis-vision, Property 3: Threshold flags follow the comparison rule
@settings(max_examples=200)
@given(boundary=finite_floats)
def test_boundary_equality_is_inclusive_above_exclusive_below(
    boundary: float,
) -> None:
    """At score == threshold: at-or-above flags, below does not."""
    assert flag_at_or_above(boundary, boundary) is True
    assert flag_below(boundary, boundary) is False
