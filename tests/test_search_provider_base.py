"""Unit tests for the search-provider base contract (Task 3.1).

These verify the uniform provider interface that makes the Search Hub
plug-and-play (Requirements 6.1, 6.7) and the common normalized result structure
every provider returns (Requirement 6.3): the category enum alignment, the
read-only request/result value objects and their validation, runtime protocol
conformance, and the failure/outcome aggregates used for failure isolation
(Requirements 6.4, 6.5).
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.models.enums import ProviderCategory
from app.search_providers.base import (
    NormalizedResult,
    ProviderFailure,
    SearchCategory,
    SearchOutcome,
    SearchProvider,
    SearchRequest,
)


# --------------------------------------------------------------------------- #
# SearchCategory                                                              #
# --------------------------------------------------------------------------- #
def test_search_category_is_provider_category_alias():
    """SearchCategory shares one source of truth with the persisted enum."""
    assert SearchCategory is ProviderCategory


def test_search_category_has_the_four_labels():
    assert {c.value for c in SearchCategory} == {"general", "image", "map", "social"}


# --------------------------------------------------------------------------- #
# SearchRequest                                                               #
# --------------------------------------------------------------------------- #
def test_request_accepts_text_query():
    req = SearchRequest(query="eiffel tower")
    assert req.query == "eiffel tower"
    assert req.image_bytes is None


def test_request_accepts_image_bytes():
    req = SearchRequest(image_bytes=b"\xff\xd8\xff")
    assert req.image_bytes == b"\xff\xd8\xff"


def test_request_requires_query_or_image():
    with pytest.raises(ValueError):
        SearchRequest()


def test_request_rejects_negative_limit():
    with pytest.raises(ValueError):
        SearchRequest(query="x", limit=-1)


def test_request_allows_zero_limit():
    assert SearchRequest(query="x", limit=0).limit == 0


def test_request_coerces_category_string():
    req = SearchRequest(query="x", category="image")
    assert req.category is ProviderCategory.IMAGE


def test_request_params_are_read_only():
    req = SearchRequest(query="x", params={"region": "fr"})
    assert req.params["region"] == "fr"
    with pytest.raises(TypeError):
        req.params["region"] = "us"  # type: ignore[index]


def test_request_params_are_copied_from_source():
    source = {"a": 1}
    req = SearchRequest(query="x", params=source)
    source["a"] = 2
    assert req.params["a"] == 1


# --------------------------------------------------------------------------- #
# NormalizedResult                                                            #
# --------------------------------------------------------------------------- #
def test_normalized_result_minimal_fields():
    r = NormalizedResult(title="A page", source="duck")
    assert r.title == "A page"
    assert r.source == "duck"
    assert r.url is None
    assert r.published_date is None
    assert r.score is None
    assert dict(r.raw) == {}


def test_normalized_result_full_fields():
    when = datetime(2020, 1, 1, tzinfo=timezone.utc)
    r = NormalizedResult(
        title="A page",
        source="duck",
        url="https://example.com",
        snippet="hello",
        image_url="https://example.com/i.jpg",
        published_date=when,
        score=87.5,
        raw={"extra": 1},
    )
    assert r.url == "https://example.com"
    assert r.published_date == when
    assert r.score == 87.5
    assert r.raw["extra"] == 1


def test_normalized_result_requires_title():
    with pytest.raises(ValueError):
        NormalizedResult(title="", source="duck")


def test_normalized_result_requires_source():
    with pytest.raises(ValueError):
        NormalizedResult(title="A page", source="")


def test_normalized_result_raw_is_read_only():
    r = NormalizedResult(title="t", source="s", raw={"k": "v"})
    with pytest.raises(TypeError):
        r.raw["k"] = "other"  # type: ignore[index]


# --------------------------------------------------------------------------- #
# SearchProvider protocol                                                     #
# --------------------------------------------------------------------------- #
class _ConformingProvider:
    name = "fake-general"
    category = SearchCategory.GENERAL
    timeout_seconds = 5.0
    enabled = True

    def query(self, request: SearchRequest) -> list[NormalizedResult]:
        return [NormalizedResult(title="r", source=self.name)]


class _NonConformingProvider:
    name = "broken"
    # missing category / timeout_seconds / enabled / query


def test_conforming_provider_satisfies_protocol():
    provider = _ConformingProvider()
    assert isinstance(provider, SearchProvider)


def test_non_conforming_provider_fails_protocol_check():
    assert not isinstance(_NonConformingProvider(), SearchProvider)


def test_conforming_provider_returns_normalized_results():
    provider = _ConformingProvider()
    out = provider.query(SearchRequest(query="x"))
    assert all(isinstance(r, NormalizedResult) for r in out)
    assert out[0].source == "fake-general"


# --------------------------------------------------------------------------- #
# ProviderFailure                                                             #
# --------------------------------------------------------------------------- #
def test_provider_failure_requires_name_and_reason():
    with pytest.raises(ValueError):
        ProviderFailure(name="", reason="boom")
    with pytest.raises(ValueError):
        ProviderFailure(name="p", reason="")


def test_provider_failure_timeout_factory():
    f = ProviderFailure.timeout("slow", 3.0, category=SearchCategory.IMAGE)
    assert f.timed_out is True
    assert f.name == "slow"
    assert "3.0" in f.reason
    assert f.category is ProviderCategory.IMAGE


def test_provider_failure_error_factory_from_exception():
    f = ProviderFailure.error("p", ValueError("bad payload"))
    assert f.timed_out is False
    assert f.reason == "ValueError: bad payload"


def test_provider_failure_error_factory_from_string():
    f = ProviderFailure.error("p", "connection refused")
    assert f.reason == "connection refused"


def test_provider_failure_coerces_category_string():
    f = ProviderFailure(name="p", reason="boom", category="social")
    assert f.category is ProviderCategory.SOCIAL


# --------------------------------------------------------------------------- #
# SearchOutcome                                                               #
# --------------------------------------------------------------------------- #
def test_outcome_defaults_are_empty():
    outcome = SearchOutcome()
    assert outcome.results == []
    assert outcome.failures == []
    assert outcome.succeeded is True
    assert outcome.partial is False


def test_outcome_succeeded_when_no_failures():
    outcome = SearchOutcome(
        results=[NormalizedResult(title="t", source="s")], failures=[]
    )
    assert outcome.succeeded is True
    assert outcome.partial is False


def test_outcome_partial_when_some_results_and_some_failures():
    outcome = SearchOutcome(
        results=[NormalizedResult(title="t", source="s")],
        failures=[ProviderFailure(name="p", reason="boom")],
    )
    assert outcome.succeeded is False
    assert outcome.partial is True


def test_outcome_all_failed_is_not_partial():
    outcome = SearchOutcome(
        results=[], failures=[ProviderFailure(name="p", reason="boom")]
    )
    assert outcome.succeeded is False
    assert outcome.partial is False
