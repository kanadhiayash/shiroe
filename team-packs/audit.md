---
name: audit
agents: 3
max_agents: 4
read_only: false
description: Reader + Linter + Quality gate. For pre-ship QA, accessibility audit, code review.
output_dir: team/
---

# audit team pack

> Sourced from SHIROE_OS §8.

## Roster

| Role | Responsibility |
|---|---|
| **Reader** | Surveys the codebase / artifact. Builds a map of what exists and what changed. Writes `team/audit-survey.md`. |
| **Linter** | Runs the mechanical checks: style, types, accessibility (axe), unused code, dead imports. Writes `team/audit-lint.md`. |
| **Quality gate** | Runs `references/shiroe-qa-gate.md` checklist. Records pass/fail per item with rationale. Writes `team/audit-verdict.md`. |

## When to use

- Pre-ship QA pass
- Accessibility audit (a11y)
- Code review for an external contributor's PR
- Periodic codebase health check

## Activation

`/team audit`

Optional args:
- `--scope=<path>` — limit audit to a path
- `--diff` — audit only the working-tree diff vs base branch

## Outputs

| File | Owner |
|---|---|
| `team/audit-survey.md` | Reader |
| `team/audit-lint.md` | Linter |
| `team/audit-verdict.md` | Quality gate |

## Rules

- Quality gate decides ship / no-ship. User can override but the override is recorded in `memory/DECISIONS.md` with rationale.
- Every `fail` verdict needs a concrete fix suggestion.
- Linter must use the project's existing toolchain (ESLint config, ruff config, etc.). Do NOT invent new rules.
- Reader's survey must NOT propose changes — that's Quality gate's job.
