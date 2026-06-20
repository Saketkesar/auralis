"""Property-based test for the ranking/cap utility (Task 2.5).

Exercises ``app.utils.ranking.rank_and_cap`` against arbitrary lists of scored
candidates and arbitrary non-negative limits, asserting the four guarantees the
ranked-output requirements depend on: the result is capped to the limit, ordered
non-increasing by score, drawn only from the input (no fabrication), and leaves
the input unmutated.
"""
from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from app.utils.ranking import rank_and_cap


# A scored candidate is a small dict carrying a "score" the default extractor
# reads. Scores may be ints, floats, or ``None`` (which ranks last), and an
# "id" tag lets us distinguish otherwise-equal elements when checking membership.
_scores = st.one_of(
    st.none(),
    st.integers(min_value=-1000, max_value=1000),
    st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False),
)

_candidates = st.lists(
    st.fixed_dictionaries({"id": st.integers(), "score": _scores}),
    max_size=50,
)

_limits = st.integers(min_value=0, max_value=60)


def _rank_value(score: object) -> float:
    """Mirror rank_and_cap's ordering: ``None`` sorts below every number."""
    return float("-inf") if score is None else float(score)


# Feature: auralis-vision, Property 2: Ranked candidate lists are capped and sorted descending
# Validates: Requirements 3.4, 4.2, 8.4, 9.4
@settings(max_examples=200)
@given(candidates=_candidates, limit=_limits)
def test_ranked_lists_are_capped_and_sorted_descending(candidates, limit):
    original = [dict(c) for c in candidates]

    result = rank_and_cap(candidates, limit)

    # (1) result length <= limit
    assert len(result) <= limit

    # (2) result is sorted non-increasing by score
    scores = [_rank_value(c["score"]) for c in result]
    assert all(scores[i] >= scores[i + 1] for i in range(len(scores) - 1))

    # (3) every result element comes from the input (no fabrication). Compare by
    # object identity so duplicates and fabricated elements are both caught.
    input_ids = [id(c) for c in candidates]
    used = list(input_ids)
    for element in result:
        assert id(element) in used
        used.remove(id(element))  # each input element appears at most once

    # (4) input is not mutated (neither the list nor its elements).
    assert candidates == original
    assert [id(c) for c in candidates] == input_ids


# Feature: auralis-vision, Property 2: Ranked candidate lists are capped and sorted descending
# Validates: Requirements 3.4, 4.2, 8.4, 9.4
@settings(max_examples=100)
@given(candidates=_candidates)
def test_no_limit_returns_full_sorted_input(candidates):
    """With ``limit=None`` the result is the whole input, sorted, nothing dropped."""
    original = [dict(c) for c in candidates]

    result = rank_and_cap(candidates, None)

    assert len(result) == len(candidates)
    scores = [_rank_value(c["score"]) for c in result]
    assert all(scores[i] >= scores[i + 1] for i in range(len(scores) - 1))
    assert candidates == original
