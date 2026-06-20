"""Search-provider base contract (Task 3.1).

This module defines the *uniform Provider interface* that makes the Search Hub
plug-and-play (Requirements 6.1, 6.7). Every general / image / map / social
provider implements the same :class:`SearchProvider` protocol, returns the same
:class:`NormalizedResult` structure (Requirement 6.3), and is dispatched and
aggregated identically by the Hub.

The pieces defined here:

* :data:`SearchCategory` — the provider category. It is an alias of
  :class:`app.models.enums.ProviderCategory` so the in-memory provider contract
  and the persisted ``provider_config.category`` column share one source of
  truth (general / image / map / social).
* :class:`SearchRequest` — the read-only query handed to a provider. It carries
  a text query and/or image bytes (image and reverse-image search submit bytes),
  an optional result cap, and a free-form ``params`` bag for provider extras.
* :class:`NormalizedResult` — the common result structure every provider returns,
  so heterogeneous third-party responses correlate uniformly (Requirement 6.3).
* :class:`SearchProvider` — the runtime-checkable protocol a provider satisfies.
* :class:`ProviderFailure` — a recorded provider error or timeout (Req 6.4, 6.5).
* :class:`SearchOutcome` — the aggregate the Hub returns: normalized results from
  the providers that succeeded plus the failures from those that did not.

As with the analysis-engine contract, the Hub treats *all* provider responses as
untrusted (design DD-3): the failure/outcome types let the Hub record a bad
provider and keep the rest of the results rather than aborting the search.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping, Protocol, runtime_checkable

from app.models.enums import ProviderCategory

__all__ = [
    "SearchCategory",
    "SearchRequest",
    "NormalizedResult",
    "SearchProvider",
    "ProviderFailure",
    "SearchOutcome",
]


# The provider category and the persisted ``provider_config.category`` column are
# the same concept; alias the canonical enum rather than redeclaring it so the
# four labels (general/image/map/social) can never drift apart.
SearchCategory = ProviderCategory


@dataclass(frozen=True)
class SearchRequest:
    """A read-only search request handed to one or more providers.

    A request may be text-driven, image-driven, or both:

    * General / map / social searches typically set :attr:`query` (and, for map
      lookups, a location string in :attr:`query` or :attr:`params`).
    * Image and reverse-image searches set :attr:`image_bytes` so the provider
      can submit the picture itself (Requirement 7.1).

    :attr:`limit` is an optional cap on the number of results requested; the Hub
    and downstream engines still apply their own caps (e.g. top-20) on the
    aggregated output. :attr:`params` is a free-form mapping for provider-specific
    options and is exposed as an immutable view.
    """

    query: str | None = None
    image_bytes: bytes | None = None
    category: SearchCategory | None = None
    limit: int | None = None
    params: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # A request with neither text nor an image gives a provider nothing to
        # act on; reject it early as a contract violation.
        if not self.query and not self.image_bytes:
            raise ValueError(
                "SearchRequest requires a non-empty query or image_bytes"
            )
        if self.limit is not None and self.limit < 0:
            raise ValueError(f"limit must be non-negative, got {self.limit!r}")
        if self.category is not None and not isinstance(
            self.category, ProviderCategory
        ):
            object.__setattr__(self, "category", ProviderCategory(self.category))
        # Freeze the params bag behind a read-only view so a provider cannot
        # mutate a request shared across a fan-out.
        from types import MappingProxyType

        object.__setattr__(
            self, "params", MappingProxyType(dict(self.params or {}))
        )


@dataclass(frozen=True)
class NormalizedResult:
    """The common result structure every provider returns (Requirement 6.3).

    Heterogeneous third-party responses are mapped onto this single shape so the
    Search Hub, reverse-search correlation, and the knowledge graph can treat
    every result uniformly regardless of which provider produced it.

    * :attr:`title` — human-readable result title (always present).
    * :attr:`source` — the originating provider's :attr:`SearchProvider.name`.
    * :attr:`url` / :attr:`snippet` / :attr:`image_url` / :attr:`published_date`
      — optional fields populated when the provider supplies them. The
      publication date feeds the reverse-search "oldest appearance" / timeline
      logic (Requirements 7.3, 7.5).
    * :attr:`score` — optional provider-supplied relevance score.
    * :attr:`raw` — provider-specific extras, kept as an immutable view so the
      original payload is preserved without allowing later mutation.
    """

    title: str
    source: str
    url: str | None = None
    snippet: str | None = None
    image_url: str | None = None
    published_date: datetime | None = None
    score: float | None = None
    raw: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.title:
            raise ValueError("NormalizedResult.title must be non-empty")
        if not self.source:
            raise ValueError("NormalizedResult.source must be non-empty")
        from types import MappingProxyType

        object.__setattr__(self, "raw", MappingProxyType(dict(self.raw or {})))


@runtime_checkable
class SearchProvider(Protocol):
    """The uniform provider interface registered with the Search Hub.

    Every provider — whatever third party it wraps — exposes the same four
    attributes and a single :meth:`query` method, which is what lets a new
    provider become available simply by registering it, with no changes to any
    other provider (Requirements 6.1, 6.7).

    Attributes:
        name: Unique provider identifier, also used as
            :attr:`NormalizedResult.source` and the ``provider_config.name`` key.
        category: The :data:`SearchCategory` this provider serves.
        timeout_seconds: The per-call timeout the Hub enforces; a call that
            exceeds it is recorded as a :class:`ProviderFailure` (Requirement 6.4).
        enabled: Whether the provider participates in dispatch. The Hub reads the
            effective state from ``provider_config`` and excludes disabled
            providers (Requirement 6.6).

    Implementations return a list of :class:`NormalizedResult`. The Hub owns
    failure isolation: it bounds the call by ``timeout_seconds`` and converts a
    raised error or a timeout into a :class:`ProviderFailure` (Requirements 6.4,
    6.5), so individual providers are not required to suppress their own errors.
    """

    name: str
    category: SearchCategory
    timeout_seconds: float
    enabled: bool

    def query(self, request: SearchRequest) -> list[NormalizedResult]:
        """Execute ``request`` and return this provider's normalized results."""
        ...


@dataclass(frozen=True)
class ProviderFailure:
    """A recorded provider error or timeout (Requirements 6.4, 6.5).

    When a provider raises or fails to respond within its
    :attr:`SearchProvider.timeout_seconds`, the Hub excludes its output from
    normalization and records one of these so the failure is visible in the
    :class:`SearchOutcome` without aborting the overall search.
    """

    name: str
    reason: str
    category: SearchCategory | None = None
    timed_out: bool = False

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("ProviderFailure.name must be non-empty")
        if not self.reason:
            raise ValueError("ProviderFailure.reason must be non-empty")
        if self.category is not None and not isinstance(
            self.category, ProviderCategory
        ):
            object.__setattr__(self, "category", ProviderCategory(self.category))

    @classmethod
    def timeout(
        cls,
        name: str,
        timeout_seconds: float,
        *,
        category: SearchCategory | None = None,
    ) -> "ProviderFailure":
        """Build a failure describing a provider that exceeded its timeout."""
        return cls(
            name=name,
            reason=f"timed out after {timeout_seconds}s",
            category=category,
            timed_out=True,
        )

    @classmethod
    def error(
        cls,
        name: str,
        exc: BaseException | str,
        *,
        category: SearchCategory | None = None,
    ) -> "ProviderFailure":
        """Build a failure describing a provider that raised an error."""
        reason = (
            f"{type(exc).__name__}: {exc}"
            if isinstance(exc, BaseException)
            else str(exc)
        )
        return cls(name=name, reason=reason, category=category, timed_out=False)


@dataclass(frozen=True)
class SearchOutcome:
    """The aggregate a Search Hub dispatch returns.

    Carries the normalized results from every provider that succeeded plus a
    :class:`ProviderFailure` for each that errored or timed out. The Hub never
    raises: a search across providers always yields a :class:`SearchOutcome`,
    even one whose :attr:`results` is empty because every provider failed
    (Requirements 6.4, 6.5).
    """

    results: list[NormalizedResult] = field(default_factory=list)
    failures: list[ProviderFailure] = field(default_factory=list)

    @property
    def succeeded(self) -> bool:
        """True when at least one provider returned results without failing."""
        return len(self.failures) == 0

    @property
    def partial(self) -> bool:
        """True when some providers produced results and some failed."""
        return bool(self.results) and bool(self.failures)
