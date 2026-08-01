---
name: build
agents: 3
max_agents: 4
read_only: false
description: Planner + Implementer + Reviewer. For multi-module features and new products.
output_dir: team/
---

# build team pack

> Sourced from SHIROE_OS §8.

## Roster

| Role | Responsibility |
|---|---|
| **Planner** | Decomposes the feature into module boundaries, contracts, sequencing. Writes `team/build-plan.md`. |
| **Implementer** | Executes the plan one module at a time. Writes code; updates `team/build-progress.md` per module. |
| **Reviewer** | Reviews each Implementer hand-off against the plan and against `references/shiroe-qa-gate.md`. Writes `team/build-review.md`. |

## When to use

- Multi-module features
- New product surfaces
- Cross-cutting refactors
- Anything where slipping a contract between modules would cause rework

## Activation

`/team build`

## Outputs

| File | Owner |
|---|---|
| `team/build-plan.md` | Planner |
| `team/build-progress.md` | Implementer (append per module) |
| `team/build-review.md` | Reviewer (append per module hand-off) |

## Rules

- Max 4 agents. If a 4th is needed (e.g., a Tester), promote here, do not exceed.
- Reviewer blocks Implementer hand-off if QA gate fails. User can override.
- All outputs land in files. No inline-only deliverables.
- `memory-keeper` records each completed module under `memory/DECISIONS.md`.

## Hand-off protocol

1. Planner publishes `team/build-plan.md` with module list, contracts, dependency order.
2. User reviews plan, optionally edits, approves.
3. Implementer picks next unblocked module, builds, appends to `team/build-progress.md`.
4. Reviewer reads diff + progress entry, runs QA gate, appends verdict to `team/build-review.md`.
5. On pass: `memory-keeper` records decision. Loop to step 3.
6. On fail: Implementer re-works or escalates to user.
