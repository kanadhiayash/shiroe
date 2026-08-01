"""Provider adapter registry.

Loads declarative ``<provider>.json`` mapping files shipped in this package
(plus optional user overrides) and resolves reasoning classes to concrete
models. See ``base.py`` for the file contract.
"""

from __future__ import annotations

from pathlib import Path

from shiroe.core.reasoning import ModelSpec
from shiroe.adapters.providers.base import JsonProviderAdapter, ProviderAdapter

_PKG_DIR = Path(__file__).parent
_cache: dict[str, ProviderAdapter] = {}

DEFAULT_PROVIDER = "anthropic"


def available_providers() -> tuple[str, ...]:
    return tuple(sorted(p.stem for p in _PKG_DIR.glob("*.json")))


def get_provider(provider: str = DEFAULT_PROVIDER) -> ProviderAdapter:
    if provider not in _cache:
        path = _PKG_DIR / f"{provider}.json"
        if not path.exists():
            raise KeyError(
                f"no provider adapter {provider!r} (available: {', '.join(available_providers())})"
            )
        _cache[provider] = JsonProviderAdapter(path)
    return _cache[provider]


def resolve_model(
    reasoning_class: str, provider: str = DEFAULT_PROVIDER, *, live: bool = True
) -> ModelSpec:
    """Resolve a reasoning class to a concrete model via a provider adapter.

    ``live=False`` (dry-run/local validation) lets an unverified or
    deprecated model resolve with a recorded warning instead of raising —
    see SHR-60. Nothing is sent anywhere on that path.
    """
    return get_provider(provider).resolve(reasoning_class, live=live)
