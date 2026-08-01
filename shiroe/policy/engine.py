"""Public evaluation API — the single choke point every guard consults."""

from __future__ import annotations

from typing import Iterable

from shiroe.policy.autonomy import AutonomyMode, autonomy_gate
from shiroe.policy.precedence import resolve
from shiroe.policy.schema import Action, ActionKind, Decision, PolicyLayer, Verdict


def evaluate(
    action: Action,
    stack: Iterable[PolicyLayer],
    *,
    mode: AutonomyMode = AutonomyMode.auto_safe,
) -> Decision:
    """Resolve a policy decision for ``action``.

    Order of checks:
    1. Precedence chain gives a raw verdict.
    2. If allowed but the autonomy mode requires human approval for this
       action kind (always-approval list OR mode-vs-kind mismatch), the
       verdict is downgraded to ``require_approval``.
    """
    raw = resolve(action, stack)
    if raw.verdict is not Verdict.allow:
        return raw
    if autonomy_gate(action.kind, mode):
        return raw
    return Decision(
        verdict=Verdict.require_approval,
        reason=f"{raw.reason}; but autonomy mode {mode.value!r} "
               f"requires approval for {action.kind.value!r}",
        deciding_layer=raw.deciding_layer,
    )
