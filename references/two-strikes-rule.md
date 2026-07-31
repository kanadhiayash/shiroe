# Two-Strikes Rule

> Sourced from SHIROE_OS §11 anti-pattern: "Do NOT write a new rule on the first occurrence of an error."

## Statement

**First occurrence of an error: log it. Second occurrence: promote to a rule.**

A single failure is data, not signal. Codifying behavior off one event creates rule bloat — the kind that turns AGENTS.md into a brittle scenario-spec rather than a tight constitution.

## Procedure

### Strike one
1. Note the failure in `memory/MEMORY.md` under a `## Traps observed` section with:
   - timestamp (absolute, not relative)
   - input that triggered it
   - what went wrong
   - corrective action taken in-session
2. Do NOT touch `AGENTS.md`, do NOT add a skill, do NOT write a rule.

### Strike two (same trap class within 30 days)
1. Verify pattern: are the two occurrences truly the same class, not coincidence?
2. Promote — pick the lightest mechanism that works:
   - **Skill**: if the corrective behavior is reusable and reactive
   - **Agent rule**: if a specific agent needs always-on behavior change
   - **AGENTS.md line**: if it applies system-wide and is short
   - **PRIVACY/REDACT/SHARING entry**: if it's a sensitive-data trap
3. Cross-link the new rule back to the two `MEMORY.md` entries that justified it.
4. On `/done`, `evidence-curator` grades the new rule (high if both occurrences are concrete; medium if one is fuzzy).

### Strike three+ without promotion
Surface in `/status`: "Trap class X seen N times, never promoted to rule. Promote now?"

## What this prevents

- AGENTS.md bloat from scenario-specific rules
- Skills that fire once and never again
- Rules that are irrelevant 90% of the time (anti-pattern §11)
- Reactive over-correction to a single agent slip

## What this does NOT cover

- **Security errors** — promote immediately (zero-strike). Credential leaks, PII exposure, irreversible-action mishaps go straight to rule.
- **Privacy mode violations** — promote immediately.
- **Hard policy breaches** (e.g., agent ignored PRIVACY.md mode) — promote immediately.

## Related

- `AGENTS.md` §"Memory model" — MEMORY.md is agent-written, agent-read
- `references/v4x-canon/SHIROE_OS.md` §11 — anti-patterns
- `agents/evidence-curator.md` — grades promoted rules on /done
