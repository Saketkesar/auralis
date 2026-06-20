"""Concrete built-in providers for every Search Hub category.

Each provider is a small, deterministic implementation conforming to the
``SearchProvider`` protocol. They normalize their (stubbed) responses into
``NormalizedResult`` rows so the Hub treats them uniformly. Swapping in a real
API client only requires changing that provider's ``query`` body.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import List

from app.models.enums import ProviderCategory
from app.search_providers.base import NormalizedResult, SearchRequest
from app.services import provider_registry


class _BaseProvider:
    """Shared scaffolding for the built-in stub providers."""

    name = "base"
    category = ProviderCategory.GENERAL
    timeout_seconds = 10.0
    enabled = True

    def _seed(self, request: SearchRequest) -> str:
        basis = request.query or (
            hashlib.sha256(request.image_bytes or b"").hexdigest()[:16]
        )
        return str(basis)

    def query(self, request: SearchRequest) -> List[NormalizedResult]:  # pragma: no cover - overridden
        raise NotImplementedError


class _GeneralProvider(_BaseProvider):
    category = ProviderCategory.GENERAL

    def query(self, request: SearchRequest) -> List[NormalizedResult]:
        return []


class _ImageProvider(_BaseProvider):
    category = ProviderCategory.IMAGE

    def query(self, request: SearchRequest) -> List[NormalizedResult]:
        return []


class _MapProvider(_BaseProvider):
    category = ProviderCategory.MAP

    def query(self, request: SearchRequest) -> List[NormalizedResult]:
        return []


class _SocialProvider(_BaseProvider):
    category = ProviderCategory.SOCIAL

    def query(self, request: SearchRequest) -> List[NormalizedResult]:
        return []


# --- General -------------------------------------------------------------- #
class GoogleProvider(_GeneralProvider):
    name = "google"


class BingProvider(_GeneralProvider):
    name = "bing"


class BraveProvider(_GeneralProvider):
    name = "brave"


class DuckDuckGoProvider(_GeneralProvider):
    name = "duckduckgo"


class BaiduProvider(_GeneralProvider):
    name = "baidu"


# --- Image ---------------------------------------------------------------- #
class GoogleLensProvider(_ImageProvider):
    name = "google_lens"


class BingVisualProvider(_ImageProvider):
    name = "bing_visual"


class YandexImagesProvider(_ImageProvider):
    name = "yandex_images"


class TinEyeProvider(_ImageProvider):
    name = "tineye"


# --- Map ------------------------------------------------------------------ #
class OSMProvider(_MapProvider):
    name = "openstreetmap"


class MapillaryProvider(_MapProvider):
    name = "mapillary"


# --- Social --------------------------------------------------------------- #
class RedditProvider(_SocialProvider):
    name = "reddit"


_BUILTINS = [
    GoogleProvider,
    BingProvider,
    BraveProvider,
    DuckDuckGoProvider,
    BaiduProvider,
    GoogleLensProvider,
    BingVisualProvider,
    YandexImagesProvider,
    TinEyeProvider,
    OSMProvider,
    MapillaryProvider,
    RedditProvider,
]


def register_builtin_providers() -> None:
    """Register one instance of each built-in provider with the registry."""
    for cls in _BUILTINS:
        provider_registry.register(cls())


__all__ = [cls.__name__ for cls in _BUILTINS] + ["register_builtin_providers"]
