<!-- privacy-audit: allow-file "Plugin manifest + Fairy Tail character description. Documents skill triggers using example pattern names." -->
---
name: zeref-os
version: 1.1.1
description: Zeref Memory Engine (compat identifier `zeref-os`) — local-first context and memory engine for AI-assisted work. Harness-agnostic, model-agnostic, privacy-first. Flat memory layout, per-project wiki, append-only pattern log, snapshots, on-demand team packs. Makes AI work cumulative instead of stateless across every harness.
---

# Zeref Memory Engine

Zeref is a local-first context and memory engine that plugs *into* your existing AI harness (Claude Code, Cursor, Codex, Gemini, Windsurf, Aider). It is **not itself a harness**, **not a CEO persona**, **not a kernel-level OS**. It is the persistent memory layer your AI tools should have had from day one — named after Zeref Dragneel from *Fairy Tail*, the immortal scholar who carried ancient knowledge across forms and ages.

## What Zeref does

- **Remembers**: per-project flat `memory/` wiki + append-only `PATTERNS.jsonl` + snapshots
- **Persists across harnesses**: works in Claude Code, Codex, Gemini CLI / Antigravity, Cursor, Windsurf, Aider, Hermes, Amp, Zed, Perplexity Computer, or any tool that reads markdown
- **Protects**: 3 privacy modes (exact / abstract / local-only) + REDACT.md sensitive classes + SHARING_POLICY.md connector allowlist (all OFF by default)
- **Arbitrates**: contradictions surface to the user; never silently resolved
- **Extends itself**: detects repeated patterns (Two-Strikes Rule), drafts new skills review-first to `skills/drafts/`
- **Activates teams on demand**: `/team [solo|build|research|red|audit|ship]` — max 4 agents per pack

## Entry points

- `/zeref-os:start` — session boot with context restored (hot.md → index.md)
- `/zeref-os:done` — write summary, persist decisions, refresh hot.md, conflict scan, snapshot
- `/zeref-os:stop` — end session, optional parent push, optional handoff compile
- `/zeref-os:status` — current session state + active team + pending drafts
- `/zeref-os:team` — activate a team pack
- `/zeref-os:sync-parent` — manual parent rollup
- `/zeref-os:reset-permissions` — clear session overrides
- `/zeref-os:review-skill` — review pattern-detected skill drafts

## Architecture

See `AGENTS.md` (canonical), `CLAUDE.md` (Claude shim), `GEMINI.md` (Gemini shim), `.cursor/rules/zeref.mdc`, `.windsurfrules`, `.aider.conf.yml.example`.

## Memory layout (flat)

```
memory/
  hot.md            # last 3 sessions, ≤500 words (read FIRST)
  index.md          # domain index
  MEMORY.md         # agent-written session notes
  DECISIONS.md / OPEN_QUESTIONS.md / RISKS.md / CONFLICTS.md
  archive/          # superseded entries (never deleted)
  patterns/PATTERNS.jsonl  # append-only event log
  snapshots/        # point-in-time wiki state
  sync/             # outbound and parent rollup artifacts
  raw/              # untouched source material
```

## Promise

Zeref makes AI work feel cumulative instead of stateless — in every harness, with any model, with privacy on by default.
