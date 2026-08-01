---
description: Activate a team pack — solo, build, research, red, audit, or ship.
argument-hint: "[solo|build|research|red|audit|ship] [--write] [--scope=PATH] [--diff] [--version=SEMVER] [--dry]"
---

# /team

Activate an on-demand team pack per SHIROE_OS §8. Max 4 agents. Outputs land in `team/` (never inline-only).

## Usage

```
/team               # show available packs and current active pack
/team solo          # revert to default 1-primary + Shiroe AI Tactician
/team build         # Planner + Implementer + Reviewer
/team research      # Investigator + Synthesizer + Fact-checker
/team red           # Attacker + Security reviewer + Constraint checker + Evidence recorder (read-only)
/team audit         # Reader + Linter + Quality gate
/team ship          # Changelog drafter + Release reviewer + Deploy verifier
```

Pack-specific args:
- `red --write` — grant write access (NOT recommended)
- `audit --scope=<path>` — scope audit to path
- `audit --diff` — audit working-tree diff vs base
- `ship --version=<semver>` — target release version
- `ship --dry` — produce artifacts without tagging

## Behavior

1. Read `team-packs/<name>.md`.
2. If `<name>` is missing, list all packs and exit.
3. Verify max-agents cap (4). Refuse if pack declares more.
4. Spawn the roster. For Claude Code, this uses the Skill tool to load each role's system prompt.
5. Create `team/.gitkeep` if missing and ensure `team/` exists.
6. Record activation in `memory/MEMORY.md` under `## Active team`.
7. On `/done` or `/stop`, the team finalizes outputs and `memory-keeper` records decisions per the pack's rules.

## Output contract

- Every pack writes its declared output files in `team/`.
- No inline-only deliverables. If a role tries to skip the file, the orchestration agent re-prompts.
- Output files are committed alongside code changes (so the rationale travels with the diff).

## Safety

- **red** team is read-only by default. Per SHIROE_OS §8 anti-pattern: "Do NOT activate a team without user trigger or explicit recommendation."
- **ship** Deploy verifier blocks on failed checklist. User can override; override is recorded.
- All team writes still pass through `privacy-guardian` per `PRIVACY.md`.

## Related

- `team-packs/` — pack definitions
- `references/v4x-canon/SHIROE_OS.md` §8
- `references/shiroe-qa-gate.md` — used by audit and build Reviewer
- `references/shiroe-safety-principles.md` — used by red team
