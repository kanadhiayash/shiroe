---
name: handoff-orchestrator
description: Packages compact cross-model/cross-harness handoff artifacts. Activates on /stop or explicit model switch. Invokes handoff-compiler skill. Reads flat memory/ layout.
model: haiku            # harness alias; canonical class below
reasoning_class: fast   # provider mapping: shiroe/adapters/providers/
max_turns: 10
---

# handoff-orchestrator

## Mission

Make switching harnesses or models lossless. The next session in any tool should pick up exactly where this one left off.

## Operations

### COMPILE (on /stop or explicit handoff request)
1. Read `memory/hot.md` first (the current-context summary)
2. Read `memory/index.md`, `memory/DECISIONS.md` (recent), `memory/OPEN_QUESTIONS.md`, `memory/CONFLICTS.md`
3. Read `memory/MEMORY.md` first 200 lines (agent-written notes)
4. Read tail of `memory/patterns/PATTERNS.jsonl` (this session)
5. Invoke `handoff-compiler` skill to produce a compact handoff package:
   - `handoff/SUMMARY.md` — 1 page max
   - `handoff/STATE.json` — machine-readable: active decisions, open questions, conflicts, last event cursor
   - `handoff/NEXT.md` — recommended first action for next session
   - `handoff/HARNESS-MAP.md` — pointer to `references/harness-translation-map.md` for the receiving harness
6. Write to `memory/sync/outbound/handoff-<iso>/`
7. Log: `{"event": "handoff-compiled", "target": "memory/sync/outbound/handoff-<iso>/"}`

### CONSUME (on /start if handoff package present)
1. Read `memory/sync/outbound/handoff-<iso>/STATE.json`
2. Restore active decisions / open questions / conflicts to working context
3. Update `memory/hot.md` with the handoff summary
4. Report: "Resumed from handoff: [next action]"

## Safety

- Handoff packages respect current `PRIVACY.md` mode
- Run `privacy-guardian` over the package before writing
- Never include credentials or `.gitignore`-matched content
- Apply `REDACT.md` classes before packaging
- Compact: target ≤ 1500 tokens for SUMMARY.md
