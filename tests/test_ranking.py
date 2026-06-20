"""Unit tests for the ranking/cap utility (Task 2.4).

Covers Requirements 3.4, 4.2, 8.4, 9.4: candidate lists are returned using only
input elements, sorted non-increasing by score, and capped to a configured
limit.
"""
from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.utils.ranking import rank_and_cap


@dataclass
class Candidate:
    name: str
    score: float | None = None
    confidence: float | None = None


def test_sorts_descending_by_score():
    items = [Candidate("a", 10.0), Candidate("b", 90.0), Candidate("c", 50.0)]
    ranked = rank_and_cap(items, limit=None)
    assert [c.name for c in ranked] == ["b", "c", "a"]


def test_caps_to_configured_limit():
    items = [Candidate(f"c{i}", float(i)) for i in range(50)]
    ranked = rank_and_cap(items, limit=20)
    assert len(ranked) == 20
    # The 20 highest scores (49..30) in descending order.
    assert [c.score for c in ranked] == [float(i) for i in range(49, 29, -1)]


def test_returns_only_input_elements():
    items = [Candidate("a", 10.0), Candidate("b", 20.0)]
    ranked = rank_and_cap(items, limit=5)
    for element in ranked:
        assert element in items
    # No fabrication: result is a subset of the input identities.
    assert {id(c) for c in ranked}.issubset({id(c) for c in items})


def test_limit_zero_yields_empty_list():
    items = [Candidate("a", 10.0), Candidate("b", 20.0)]
    assert rank_and_cap(items, limit=0) == []


def test_limit_larger_than_input_returns_all():
    items = [Candidate("a", 10.0), Candidate("b", 20.0)]
    ranked = rank_and_cap(items, limit=100)
    assert len(ranked) == 2
    assert [c.name for c in ranked] == ["b", "a"]


def test_empty_input_returns_empty():
    assert rank_and_cap([], limit=20) == []


def test_negative_limit_raises():
    with pytest.raises(ValueError):
        rank_and_cap([Candidate("a", 1.0)], limit=-1)


def test_ties_preserve_input_order():
    # Equal scores must keep their original relative order (stable sort).
    items = [Candidate("a", 50.0), Candidate("b", 50.0), Candidate("c", 50.0)]
    ranked = rank_and_cap(items, limit=None)
    assert [c.name for c in ranked] == ["a", "b", "c"]


def test_none_scores_rank_last():
    items = [Candidate("a", None), Candidate("b", 10.0), Candidate("c", None)]
    ranked = rank_and_cap(items, limit=None)
    assert ranked[0].name == "b"
    # The two None-scored elements follow, in input order.
    assert [c.name for c in ranked[1:]] == ["a", "c"]


def test_confidence_attribute_used_as_fallback():
    items = [Candidate("a", confidence=5.0), Candidate("b", confidence=80.0)]
    ranked = rank_and_cap(items, limit=None)
    assert [c.name for c in ranked] == ["b", "a"]


def test_dict_candidates_with_score_key():
    items = [{"name": "a", "score": 30.0}, {"name": "b", "score": 70.0}]
    ranked = rank_and_cap(items, limit=None)
    assert [c["name"] for c in ranked] == ["b", "a"]


def test_custom_key_function():
    items = [("a", 3), ("b", 9), ("c", 1)]
    ranked = rank_and_cap(items, limit=2, key=lambda t: t[1])
    assert ranked == [("b", 9), ("a", 3)]


def test_does_not_mutate_input():
    items = [Candidate("a", 10.0), Candidate("b", 20.0)]
    snapshot = list(items)
    rank_and_cap(items, limit=1)
    assert items == snapshot


def test_accepts_generator_input():
    gen = (Candidate(f"c{i}", float(i)) for i in range(5))
    ranked = rank_and_cap(gen, limit=3)
    assert [c.score for c in ranked] == [4.0, 3.0, 2.0]
