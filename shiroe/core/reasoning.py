"""Provider-neutral reasoning classes (vNext ADR-0002).

Core code and canonical schemas never name provider models. Tasks carry a
criticality; criticality resolves to a reasoning class; a provider adapter
(shiroe/adapters/providers/) maps the class to a concrete model at the edge.

Hard rules enforced here, not in prose:
- ``frontier`` is reserved for CRITICAL tasks.
- LOW tasks always resolve to ``fast`` — never anything costlier.
"""

from __future__ import annotations

from dataclasses import dataclass

# The six canonical reasoning classes (SHIROE vNext §3.5).
FAST = "fast"
BALANCED = "balanced"
DEEP = "deep"
FRONTIER = "frontier"
LOCAL = "local"
PRIVATE = "private"

REASONING_CLASSES: tuple[str, ...] = (FAST, BALANCED, DEEP, FRONTIER, LOCAL, PRIVATE)

# Task criticality vocabulary (matches shiroe.routing weights).
CRITICALITIES: tuple[str, ...] = ("LOW", "MEDIUM", "HIGH", "CRITICAL")

# Criticality → reasoning class. The only map that decides how much
# reasoning a task may buy. frontier appears exactly once: CRITICAL.
_CRITICALITY_TO_CLASS: dict[str, str] = {
    "LOW": FAST,
    "MEDIUM": BALANCED,
    "HIGH": DEEP,
    "CRITICAL": FRONTIER,
}


class ReasoningPolicyError(ValueError):
    """Raised when a caller requests a class its criticality does not permit."""


@dataclass(frozen=True)
class ModelSpec:
    """Concrete resolution produced by a provider adapter."""

    provider: str
    model_id: str
    reasoning_class: str
    effort: str | None = None
    # SHR-60: capability verification carried on the resolved spec so callers
    # (and the gateway) can see *why* a resolution was allowed without a
    # second lookup. Defaults preserve every pre-SHR-60 construction site.
    lifecycle: str = "active"
    verified: bool = True
    warning: str | None = None


def is_reasoning_class(name: str) -> bool:
    return name in REASONING_CLASSES


def resolve_class(criticality: str) -> str:
    """Map task criticality to the reasoning class it is entitled to."""
    crit = criticality.upper()
    if crit not in _CRITICALITY_TO_CLASS:
        raise ReasoningPolicyError(
            f"unknown criticality {criticality!r}; expected one of {CRITICALITIES}"
        )
    return _CRITICALITY_TO_CLASS[crit]


def validate_request(criticality: str, requested_class: str) -> str:
    """Validate an explicit class request against criticality entitlement.

    Returns the granted class. A request may always downgrade (cheaper than
    entitled) but never upgrade: frontier requires CRITICAL, deep requires
    HIGH or above, balanced requires MEDIUM or above. ``local`` and
    ``private`` are placement constraints, not cost upgrades, and are
    permitted at any criticality.
    """
    if requested_class not in REASONING_CLASSES:
        raise ReasoningPolicyError(
            f"unknown reasoning class {requested_class!r}; expected one of {REASONING_CLASSES}"
        )
    if requested_class in (LOCAL, PRIVATE):
        return requested_class
    entitled = resolve_class(criticality)
    order = [FAST, BALANCED, DEEP, FRONTIER]
    if order.index(requested_class) > order.index(entitled):
        raise ReasoningPolicyError(
            f"criticality {criticality.upper()} entitles at most {entitled!r}; "
            f"{requested_class!r} denied (frontier is CRITICAL-only)"
        )
    return requested_class
