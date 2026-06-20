"""Built-in search providers (Task 3.7).

Lightweight, dependency-free provider implementations for each category. They
conform to the :class:`~app.search_providers.base.SearchProvider` protocol and
self-register with the provider registry on import, so the Search Hub can
dispatch to them without any other module changing (Requirements 6.1, 6.7).

These are deterministic stub providers: they return structured
:class:`NormalizedResult` rows derived from the request rather than calling live
third-party APIs (which require credentials/network). Real integrations can
replace any one of them without touching the others.
"""
from __future__ import annotations

from app.search_providers.builtin.providers import (
    BaiduProvider,
    BingProvider,
    BingVisualProvider,
    BraveProvider,
    DuckDuckGoProvider,
    GoogleProvider,
    GoogleLensProvider,
    MapillaryProvider,
    OSMProvider,
    RedditProvider,
    TinEyeProvider,
    YandexImagesProvider,
    register_builtin_providers,
)

register_builtin_providers()

__all__ = [
    "GoogleProvider",
    "BingProvider",
    "BraveProvider",
    "DuckDuckGoProvider",
    "BaiduProvider",
    "GoogleLensProvider",
    "BingVisualProvider",
    "YandexImagesProvider",
    "TinEyeProvider",
    "OSMProvider",
    "MapillaryProvider",
    "RedditProvider",
    "register_builtin_providers",
]
