---
name: handoff-compiler
description: Produces compact cross-model/cross-harness handoff package from flat memory/ layout. Invoked by handoff-orchestrator on /stop or model switch. References harness translation map.
trigger:
  - handoff-orchestrator invokes
  - /stop with handoff requested
  - user says "handoff to ..."
model: sonnet
reasoning_class: balanced
max_turns: 15
---

# handoff-compiler

## Mission

Compress current project state into a package that any harness/model can pick up. Cross-harness portability per SHIROE_OS §10 + D7.

## Output package

Written to `memory/sync/outbound/handoff-<iso>/`:

### `SUMMARY.md` (target ≤ 1500 tokens)
- Project name + 1-line description
- Last 3 decisions (titles only)
- Top 3 open questions
- Active conflicts (titles only)
- Next recommended action

### `STATE.json` (machine-readable)
```json
{
  "schema_version": "1.0",
  "project_name": "...",
  "exported_at": "ISO-8601 UTC",
  "last_event_cursor": "sha256:...",
  "active_decisions_count": 12,
  "open_questions_count": 3,
  "active_conflicts_count": 0,
  "model_tier_recommended": "Standard",
  "privacy_mode": "abstract"
}
```

### `NEXT.md`
1-page: what the next session should do first. Concrete instruction, not abstract intent.

### `HARNESS-MAP.md`
Pointer to `references/harness-translation-map.md`. Identifies the source harness and lists the per-harness load instructions for whichever harness picks this up.

## Flow

1. Read `memory/hot.md` first (current-context summary)
2. Read `memory/index.md` + `memory/DECISIONS.md` (recent) + `memory/OPEN_QUESTIONS.md` + `memory/CONFLICTS.md`
3. Read `memory/MEMORY.md` first 200 lines (agent-written notes)
4. Read session events from current session in `memory/patterns/PATTERNS.jsonl`
5. Pass everything through `privacy-guardian` per current `PRIVACY.md` mode + `REDACT.md` classes
6. Compile to package
7. Write to `memory/sync/outbound/handoff-<iso>/`
8. Log `{"event": "handoff-compiled", "target": "..."}`

## Safety

- Per `_shared/rules.md#R6` (Zero Context Loss): STATE.json + SUMMARY.md + NEXT.md must jointly cover every entity from the source session (decisions, file paths, open questions, error strings). Downstream `caveman-handoff` re-verifies the R6 diff before compression.
- Target ≤ 1500 tokens for SUMMARY.md (the always-on portion the next session loads)
- Never include credentials or `.gitignore`-matched content
- Respect privacy mode and connector allowlist
- Run `privacy-guardian` over the package BEFORE writing to outbound
