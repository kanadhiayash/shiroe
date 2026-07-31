"""Deprecation alias map for the vNext terminology pivot (one release cycle).

Old names keep working through :func:`resolve_alias`, which warns once per
process and returns the canonical replacement. Removal target: 2.1.0.
"""

from __future__ import annotations

import warnings

# old name → (new name, category)
DEPRECATED_ALIASES: dict[str, tuple[str, str]] = {
    # execution profiles
    "small": ("lean", "execution-policy"),
    "medium": ("balanced", "execution-policy"),
    "enterprise": ("assured", "execution-policy"),
    # component renames
    "skill-router": ("capability-resolver", "component"),
    "fleet-activator": ("capability-prober", "component"),
    "skill-importer": ("capability-manager", "component"),
    # model tier aliases → reasoning classes (provider mapping lives in adapters)
    "haiku": ("fast", "reasoning-class"),
    "sonnet": ("balanced", "reasoning-class"),
    "opus": ("deep", "reasoning-class"),
}

_warned: set[str] = set()


def resolve_alias(name: str) -> str:
    """Return the canonical name, warning once if ``name`` is deprecated."""
    entry = DEPRECATED_ALIASES.get(name)
    if entry is None:
        return name
    new, category = entry
    if name not in _warned:
        _warned.add(name)
        warnings.warn(
            f"{category} name {name!r} is deprecated; use {new!r} "
            f"(see docs/DEPRECATIONS.md; alias removed in 2.1.0)",
            DeprecationWarning,
            stacklevel=2,
        )
    return new
