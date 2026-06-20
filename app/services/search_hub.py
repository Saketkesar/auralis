"""Search Hub (Task 3.4; Requirements 6.2-6.6).

Dispatches a :class:`SearchRequest` to every enabled provider in a category,
bounds each provider call by its own timeout, normalizes successes into the
common :class:`NormalizedResult` structure, and records per-provider timeouts
and errors as :class:`ProviderFailure` without aborting the overall search. The
Hub never raises: a dispatch always returns a :class:`SearchOutcome`.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from typing import List, Optional

from app.models.enums import ProviderCategory
from app.search_providers.base import (
    NormalizedResult,
    ProviderFailure,
    SearchOutcome,
    SearchProvider,
    SearchRequest,
)
from app.services import provider_registry


class SearchHub:
    """Fan-out/fan-in dispatcher across pluggable providers."""

    def __init__(self, session=None, default_timeout: float = 10.0) -> None:
        self._session = session
        self._default_timeout = default_timeout

    def search(
        self,
        category: ProviderCategory | str,
        request: SearchRequest,
        *,
        providers: Optional[List[SearchProvider]] = None,
    ) -> SearchOutcome:
        cat = (
            category
            if isinstance(category, ProviderCategory)
            else ProviderCategory(category)
        )
        targets = (
            providers
            if providers is not None
            else provider_registry.providers_for(cat, self._session)
        )

        results: List[NormalizedResult] = []
        failures: List[ProviderFailure] = []

        # Run providers concurrently; isolate each behind its own timeout.
        with ThreadPoolExecutor(max_workers=max(1, len(targets) or 1)) as pool:
            futures = {pool.submit(p.query, request): p for p in targets}
            for future, provider in list(futures.items()):
                timeout = getattr(provider, "timeout_seconds", self._default_timeout)
                try:
                    provider_results = future.result(timeout=timeout)
                except FuturesTimeout:
                    failures.append(
                        ProviderFailure.timeout(
                            provider.name, timeout, category=cat
                        )
                    )
                    future.cancel()
                except Exception as exc:  # noqa: BLE001 - isolate provider errors
                    failures.append(
                        ProviderFailure.error(provider.name, exc, category=cat)
                    )
                else:
                    for r in provider_results or []:
                        if isinstance(r, NormalizedResult):
                            results.append(r)

        return SearchOutcome(results=results, failures=failures)


__all__ = ["SearchHub"]
