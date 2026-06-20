"""Pluggable search providers package.

Holds the provider base contract (:mod:`app.search_providers.base`) and, under
``builtin/``, the general/image/map/social providers. Providers conform to the
:class:`~app.search_providers.base.SearchProvider` protocol and register with the
Search Hub so a new provider becomes available without changes to existing ones
(Requirements 6.1, 6.7).
"""
from app.search_providers.base import (
    NormalizedResult,
    ProviderFailure,
    SearchCategory,
    SearchOutcome,
    SearchProvider,
    SearchRequest,
)

__all__ = [
    "SearchCategory",
    "SearchRequest",
    "NormalizedResult",
    "SearchProvider",
    "ProviderFailure",
    "SearchOutcome",
]
