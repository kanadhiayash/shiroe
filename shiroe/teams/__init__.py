"""Team compiler + resolver (vNext PR 7, master plan §9.3).

Given (task_id, mission, policy, active_harness), the compiler:

1. Reads every approved capability from the registry (PR 4).
2. For each mission seat, scores every capability against the seat's
   requirements using the 13 factors in master plan §8.7.
3. Enforces independence constraints (e.g. verifier `independent_from:
   [implementer]`) — self-review is refused, not silently allowed.
4. Persists the compiled plan to `team_runs`, `team_assignments`, and
   `execution_steps` (schemas landed in PR 2).

No supervisor here; PR 8 owns execution.
"""

from shiroe.teams.plan import CompiledTeamPlan
from shiroe.teams.resolver import (
    NoEligibleCapabilityError,
    SelfReviewError,
    resolve_seat,
    score_capability,
)
from shiroe.teams.compiler import compile_team

__all__ = [
    "CompiledTeamPlan",
    "NoEligibleCapabilityError", "SelfReviewError",
    "resolve_seat", "score_capability",
    "compile_team",
]
