"""Capability lifecycle state machine (vNext §8.2, ADR-0004)."""

from __future__ import annotations


LIFECYCLE_STATES = (
    "discovered",
    "quarantined",
    "inspected",
    "approved",
    "benchmarked",
    "active",
    "stale",
    "revoked",
    "compromised",
)

# Only these states may be executed. discovered/quarantined/inspected are
# pre-approval; stale/revoked/compromised are post-active.
EXECUTABLE_STATES = frozenset({"approved", "benchmarked", "active"})

_TRANSITIONS: dict[str, frozenset[str]] = {
    "discovered": frozenset({"quarantined"}),
    "quarantined": frozenset({"inspected", "revoked"}),
    "inspected": frozenset({"approved", "revoked", "quarantined"}),
    "approved": frozenset({"benchmarked", "active", "stale", "revoked",
                            "compromised", "quarantined"}),
    "benchmarked": frozenset({"active", "stale", "revoked", "compromised",
                               "quarantined"}),
    "active": frozenset({"stale", "revoked", "compromised", "quarantined"}),
    "stale": frozenset({"active", "revoked", "quarantined"}),
    "revoked": frozenset(),  # terminal
    "compromised": frozenset({"revoked", "quarantined"}),
}


class InvalidTransition(ValueError):
    pass


def can_transition(current: str, target: str) -> bool:
    if current not in _TRANSITIONS:
        return False
    return target in _TRANSITIONS[current]


def transition(current: str, target: str) -> str:
    if not can_transition(current, target):
        raise InvalidTransition(
            f"invalid capability lifecycle transition: {current!r} → {target!r}"
        )
    return target


def is_executable(state: str) -> bool:
    return state in EXECUTABLE_STATES


def next_state_for_digest_change(current: str) -> str:
    """Any state that would allow execution snaps back to ``quarantined``
    the moment the source digest drifts. Terminal states stay put."""
    if current in ("revoked",):
        return current
    return "quarantined"
