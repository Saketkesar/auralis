"""Unit tests for the threshold-flag utility (Task 2.6).

These verify the two comparison rules used by the alert-raising engines:

* ``flag_at_or_above`` -- AI-image (13.4) and threat (17.4) alerts fire when the
  score meets *or exceeds* the threshold (boundary inclusive).
* ``flag_below`` -- the deepfake authenticity alert (14.3) fires when the score
  falls *strictly below* the threshold (boundary exclusive).
"""
from __future__ import annotations

from app.utils.thresholds import flag_at_or_above, flag_below


class TestFlagAtOrAbove:
    def test_above_threshold_flags(self):
        assert flag_at_or_above(80.0, 70.0) is True

    def test_below_threshold_does_not_flag(self):
        assert flag_at_or_above(60.0, 70.0) is False

    def test_equal_to_threshold_flags(self):
        # "meets the configured alert threshold" includes equality.
        assert flag_at_or_above(70.0, 70.0) is True

    def test_zero_threshold_flags_everything_nonnegative(self):
        assert flag_at_or_above(0.0, 0.0) is True
        assert flag_at_or_above(0.1, 0.0) is True

    def test_hundred_threshold_only_max_flags(self):
        assert flag_at_or_above(100.0, 100.0) is True
        assert flag_at_or_above(99.999, 100.0) is False


class TestFlagBelow:
    def test_below_threshold_flags(self):
        assert flag_below(60.0, 70.0) is True

    def test_above_threshold_does_not_flag(self):
        assert flag_below(80.0, 70.0) is False

    def test_equal_to_threshold_does_not_flag(self):
        # "falls below the configured alert threshold" excludes equality.
        assert flag_below(70.0, 70.0) is False

    def test_zero_score_below_positive_threshold_flags(self):
        assert flag_below(0.0, 50.0) is True

    def test_zero_threshold_never_flags(self):
        assert flag_below(0.0, 0.0) is False
        assert flag_below(50.0, 0.0) is False


class TestComplementarity:
    """At-or-above and below partition the space at the same boundary."""

    def test_exactly_one_rule_holds_for_each_pair(self):
        for score, threshold in [(0.0, 0.0), (50.0, 50.0), (49.9, 50.0), (50.1, 50.0)]:
            assert flag_at_or_above(score, threshold) != flag_below(score, threshold)
