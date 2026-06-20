"""Provider registry (Task 3.2; Requirements 6.6, 6.7).

A plug-and-play registry of search providers. Providers self-register via
:func:`register`; the Search Hub asks for the enabled providers of a category
via :func:`providers_for`. Enable state is persisted to ``provider_config`` when
a database session is available, with an in-memory fallback otherwise so the
registry works in tests and during boot before the DB is provisioned.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from app.models.enums import ProviderCategory
from app.search_providers.base import SearchProvider

# In-process registry of all known providers keyed by name.
_REGISTRY: Dict[str, SearchProvider] = {}
# In-memory enable-state fallback used when no DB session is supplied.
_ENABLED: Dict[str, bool] = {}


def register(provider: SearchProvider) -> SearchProvider:
    """Register a provider, making it available without touching others."""
    _REGISTRY[provider.name] = provider
    _ENABLED.setdefault(provider.name, getattr(provider, "enabled", True))
    return provider


def unregister(name: str) -> None:
    _REGISTRY.pop(name, None)
    _ENABLED.pop(name, None)


def all_providers() -> List[SearchProvider]:
    return list(_REGISTRY.values())


def is_enabled(name: str, session=None) -> bool:
    """Resolve enable state from provider_config, falling back to memory."""
    if session is not None:
        row = _config_row(session, name)
        if row is not None:
            return bool(row.enabled)
    return _ENABLED.get(name, True)


def providers_for(
    category: ProviderCategory | str, session=None
) -> List[SearchProvider]:
    """Return the enabled providers registered for ``category``."""
    cat = category if isinstance(category, ProviderCategory) else ProviderCategory(category)
    return [
        p
        for p in _REGISTRY.values()
        if p.category == cat and is_enabled(p.name, session)
    ]


def set_enabled(name: str, enabled: bool, session=None) -> None:
    """Persist a provider's enable state (DB when available, else memory)."""
    _ENABLED[name] = bool(enabled)
    if session is None:
        return
    from app.models.provider_config import ProviderConfig

    row = _config_row(session, name)
    if row is None:
        provider = _REGISTRY.get(name)
        category = provider.category if provider else ProviderCategory.GENERAL
        row = ProviderConfig(name=name, category=category, enabled=bool(enabled))
        session.add(row)
    else:
        row.enabled = bool(enabled)
    session.commit()


def _config_row(session, name: str):
    from app.models.provider_config import ProviderConfig

    return (
        session.query(ProviderConfig)
        .filter(ProviderConfig.name == name)
        .one_or_none()
    )


def clear() -> None:
    """Test helper: drop all in-memory registrations."""
    _REGISTRY.clear()
    _ENABLED.clear()


__all__ = [
    "register",
    "unregister",
    "all_providers",
    "providers_for",
    "is_enabled",
    "set_enabled",
    "clear",
]
