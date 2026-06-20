"""Unit tests for the bounded scoring utility (Task 2.2).

These cover specific examples and edge cases for ``bounded_score``: the in-range
pass-through, clamping of out-of-range numbers, the boundary values, and sensible
handling of non-finite and missing inputs. The universal "always in [0, 100]"
invariant is covered separately by the property test in Task 2.3.

Validates Requirements 2.5, 3.3, 4.3, 8.5, 9.3, 12.4, 13.2, 14.2, 15.3, 17.2, 18.4.
"""
from __future__ import annotations

import math

import pytest

from app.utils.scoring import SCORE_MAX, SCORE_MIN, bounded_score


class TestInRangeValues:
    @pytest.mark.parametrize("value", [0, 0.0, 1, 42, 42.5, 99.999, 100, 100.0])
    def test_in_range_values_pass_through(self, value):
        assert bounded_score(value) == float(value)

    def test_result_is_always_float(self):
        assert isinstance(bounded_score(50), float)
        assert isinstance(bounded_score(0), float)


class TestBoundaries:
    def test_exact_lower_bound(self):
        assert bounded_score(0) == SCORE_MIN

    def test_exact_upper_bound(self):
        assert bounded_score(100) == SCORE_MAX


class TestClamping:
    def test_negative_clamps_to_zero(self):
        assert bounded_score(-1) == SCORE_MIN
        assert bounded_score(-9999.5) == SCORE_MIN

    def test_above_max_clamps_to_hundred(self):
        assert bounded_score(101) == SCORE_MAX
        assert bounded_score(1_000_000.0) == SCORE_MAX


class TestNonFiniteInputs:
    def test_positive_infinity_clamps_to_max(self):
        assert bounded_score(math.inf) == SCORE_MAX

    def test_negative_infinity_clamps_to_min(self):
        assert bounded_score(-math.inf) == SCORE_MIN

    def test_nan_falls_back_to_default(self):
        assert bounded_score(math.nan) == SCORE_MIN

    def test_nan_uses_supplied_default(self):
        assert bounded_score(math.nan, default=50) == 50.0


class TestNoneAndDefault:
    def test_none_falls_back_to_default(self):
        assert bounded_score(None) == SCORE_MIN

    def test_none_uses_supplied_default(self):
        assert bounded_score(None, default=73.5) == 73.5

    def test_out_of_range_default_is_clamped(self):
        # A caller cannot widen the bounds via the default.
        assert bounded_score(None, default=500) == SCORE_MAX
        assert bounded_score(None, default=-7) == SCORE_MIN


class TestInvalidTypes:
    @pytest.mark.parametrize("bad", [True, False])
    def test_bool_is_rejected(self, bad):
        with pytest.raises(TypeError):
            bounded_score(bad)

    @pytest.mark.parametrize("bad", ["50", [50], {"score": 50}, object()])
    def test_non_numeric_is_rejected(self, bad):
        with pytest.raises(TypeError):
            bounded_score(bad)

    def test_invalid_default_is_rejected(self):
        with pytest.raises(TypeError):
            bounded_score(50, default="0")
