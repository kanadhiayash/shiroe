# CODEX.md — Codex harness shim (Shiroe)

**Canonical spec: `AGENTS.md`** — read it first. This file only adds
Codex-specific notes.

## Codex-specific

- Codex CLI reads `AGENTS.md` natively. No additional configuration needed
  for basic operation.
- Slash commands resolve through the Codex command layer; refer to your
  Codex CLI version's documentation for the exact invocation syntax.
- Per-harness quirks live in `config/codex-overrides.md` (create on demand
  — not shipped by default).

## First action every session

Identical to AGENTS.md §"First action every session":

1. Read `config/PROJECT.md`
2. Read `memory/hot.md` (≤500 words)
3. Read `memory/index.md` if hot insufficient
4. Read `PRIVACY.md` (root) — before any write or tool use
5. Read `REDACT.md` (root) — before any external output
6. Tail last 3 entries of `memory/patterns/PATTERNS.jsonl`
7. Report state

## Safety

See `references/shiroe-safety-principles.md`. Irreversible actions always
require explicit user confirmation.
