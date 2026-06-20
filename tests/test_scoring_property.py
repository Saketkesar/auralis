"""Property-based tests for the bounded scoring utility (Task 2.3).

These exercise ``app.utils.scoring.bounded_score`` across a wide space of
numeric inputs - in-range, out-of-range, negative, very large, infinities, and
NaN - to confirm the single invariant every engine relies on: a produced
``Confidence_Score`` / ``Risk_Score`` always lands in the closed interval
``[0, 100]``.
"""
from __future__ import annotations

import math

from hypothesis import given, settings
from hypothesis import strategies as st

from app.utils.scoring import SCORE_MAX, SCORE_MIN, bounded_score


# Arbitrary numeric inputs spanning the interesting regions of the score space:
# in-range floats, wildly out-of-range and very large magnitudes, negatives,
# integers, and the non-finite specials (+/-inf, NaN).
_numeric_values = st.one_of(
    st.floats(allow_nan=True, allow_infinity=True),
    st.floats(min_value=-1e9, max_value=1e9),
    st.integers(min_value=-(10**18), max_value=10**18),
    st.sampled_from(
        [
            math.nan,
            math.inf,
            -math.inf,
            SCORE_MIN,
            SCORE_MAX,
            -0.0,
            -1.0,
            100.0000001,
            -0.0000001,
            1e308,
            -1e308,
        ]
    ),
)

# Defaults are themselves clamped, so any real number is a valid default and the
# result must still respect the bounds.
_default_values = st.one_of(
    st.floats(allow_nan=False, allow_infinity=False, min_value=-1e6, max_value=1e6),
    st.integers(min_value=-1000, max_value=1000),
)


# Feature: auralis-vision, Property 1: Scores are bounded to [0, 100]
# Validates: Requirements 2.5, 3.3, 4.3, 8.5, 9.3, 12.4, 13.2, 14.2, 15.3, 17.2, 18.4
@settings(max_examples=200)
@given(value=_numeric_values, default=_default_values)
def test_bounded_score_is_always_within_bounds(value: object, default: float) -> None:
    result = bounded_score(value, default=default)

    assert isinstance(result, float)
    assert math.isfinite(result)
    assert SCORE_MIN <= result <= SCORE_MAX


# Feature: auralis-vision, Property 1: Scores are bounded to [0, 100]
# Validates: Requirements 2.5, 3.3, 4.3, 8.5, 9.3, 12.4, 13.2, 14.2, 15.3, 17.2, 18.4
@settings(max_examples=200)
@given(value=_numeric_values)
def test_bounded_score_within_bounds_with_default_default(value: object) -> None:
    # The same invariant must hold when the caller relies on the built-in default.
    result = bounded_score(value)

    assert isinstance(result, float)
    assert math.isfinite(result)
    assert SCORE_MIN <= result <= SCORE_MAX


# Feature: auralis-vision, Property 1: Scores are bounded to [0, 100]
# Validates: Requirements 2.5, 3.3, 4.3, 8.5, 9.3, 12.4, 13.2, 14.2, 15.3, 17.2, 18.4
@settings(max_examples=200)
@given(value=st.none() | _numeric_values, default=_default_values)
def test_bounded_score_handles_none_within_bounds(value: object, default: float) -> None:
    # ``None`` resolves to the (clamped) default and must also stay in range.
    result = bounded_score(value, default=default)

    assert SCORE_MIN <= result <= SCORE_MAX
