<!-- privacy-audit: allow-file "Gemini harness stub references AGENTS.md + example paths." -->

# GEMINI.md — Gemini harness shim (Zeref)

**Canonical spec: `AGENTS.md`** — read it first. This file only adds Gemini-specific notes.

## Gemini-specific

- Large-context-friendly: Gemini can load full flat `memory/` in a single call. Still prefer boundary-first (hot.md → index.md → section) for token discipline.
- No native skill registry: invoke skills by reading the relevant `skills/<name>/SKILL.md` directly.
- Commands map to user prompts containing `/start`, `/done`, etc. — interpret as instruction triggers.
- Tool-state awareness: surface MCP tool availability in session boot report (per `SHARING_POLICY.md`).

## First action every session

Identical to AGENTS.md §"First action every session" (reading order per ZEREF_OS §0):
1. Read `config/PROJECT.md`
2. Read `memory/hot.md` (≤500 words)
3. Read `memory/index.md` if hot insufficient
4. Read `PRIVACY.md` (root)
5. Read `REDACT.md` (root)
6. Tail last 3 entries of `memory/patterns/PATTERNS.jsonl`
7. Report state
