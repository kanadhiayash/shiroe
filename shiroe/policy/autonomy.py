"""Autonomy modes + hardcoded require-approval list (vNext §9.5)."""

from __future__ import annotations

from enum import Enum

from shiroe.policy.schema import ActionKind


class AutonomyMode(str, Enum):
    suggest = "suggest"          # compile only; never execute
    auto_safe = "auto-safe"      # execute local, reversible, approved actions
    policy_bound = "policy-bound"  # execute anything policy allows; stop at a deny


ALWAYS_REQUIRE_APPROVAL: frozenset[ActionKind] = frozenset({
    ActionKind.push,
    ActionKind.merge,
    ActionKind.publish,
    ActionKind.external_message,
    ActionKind.fs_delete,
    ActionKind.destructive,
    ActionKind.secret_read,
    ActionKind.dependency_add,
    ActionKind.permission_change,
    ActionKind.budget_escalation,
})


REVERSIBLE_KINDS: frozenset[ActionKind] = frozenset({
    ActionKind.fs_read,
    ActionKind.memory_write,
    ActionKind.event_write,
    ActionKind.capability_invoke,
})


def autonomy_gate(kind: ActionKind, mode: AutonomyMode) -> bool:
    """Return True if ``mode`` may execute ``kind`` without prompting.

    ``suggest`` never executes.  ``auto-safe`` runs only reversible +
    non-always-approval kinds. ``policy-bound`` runs anything not on the
    always-approval list; policy denies still stop it.
    """
    if kind in ALWAYS_REQUIRE_APPROVAL:
        return False
    if mode is AutonomyMode.suggest:
        return False
    if mode is AutonomyMode.auto_safe:
        return kind in REVERSIBLE_KINDS
    return True  # policy_bound
