---
pack: small
budget_target_tokens_per_session: 25000
budget_hard_cap_tokens_per_session: 50000
default_tier: haiku
opus_allowed: false
sonnet_allowed: limited       # only when haiku quality is insufficient
agents_active: 1              # memory-keeper only
skills_active_max: 3
---

# Team Pack: small

**For:** solo work, prototyping, low-stakes decisions, cost-sensitive
sessions. The cheapest viable surface that still preserves the Zeref
invariants.

## Composition

- **1 background agent:** `memory-keeper` (the single writer).
- **Up to 3 on-trigger skills**, picked by `skill-router` per task.

## Cost envelope

- Soft target: **25k tokens / session** combined input+output.
- Hard cap: **50k tokens / session**. `budget-governor` blocks further
  spend at the cap and asks for explicit override.
- Default tier: `haiku`. `sonnet` is allowed *only* when a CRITICAL or
  HIGH-weight task self-reports a failure on `haiku`. `opus` is
  **forbidden** in this pack.

## When to use

- Quick research questions.
- Writing or editing a single document.
- Routine refactors with a known shape.
- Daily session "brain dump" + grading.

## When to upgrade to `medium`

- Cross-file refactor planned.
- Adversarial security review needed.
- More than 3 skills required to complete the task.
- `haiku` flagged as insufficient for a HIGH-weight item three sessions
  running.
