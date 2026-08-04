---
name: wiki-maintenance
description: Maintains the flat memory/ markdown surface — index consistency, page summaries, decisions log, risks register, open questions queue. Activates after writes and on consolidation requests.
trigger:
  - post-write (called by memory-keeper after every write)
  - /done (consolidation pass)
  - "update wiki"
  - "update index"
  - "consolidate memory"
  - "clean up wiki"
  - "refresh hot.md"
  - "wiki lint"
  - /wiki-maintenance
model: haiku
reasoning_class: fast
max_turns: 15
---

# wiki-maintenance

## Mission

Keep the flat `memory/` markdown surface clean, indexed, and useful.

This skill maintains an authored markdown layer, not the record of truth. Per
`docs/adr/ADR-0001-canonical-store.md`, current state lives in the local SQLite
store and history in the append-only JSONL log; `memory/views/` is generated
from those and is out of scope here — never hand-edit it.

## Operations

### POST-WRITE (called by memory-keeper after every write)
1. Update `memory/index.md` row for the affected domain
2. If page > 1500 lines → propose archival to `memory/archive/`
3. Re-grade entries via `evidence-curator` if staleness threshold crossed

### CONSOLIDATE (on /done or explicit request)
1. Scan all wiki pages (`memory/index.md`, `memory/DECISIONS.md`, `memory/OPEN_QUESTIONS.md`, `memory/RISKS.md`, `memory/CONFLICTS.md`)
2. Merge duplicate decisions
3. Move resolved questions to `memory/DECISIONS.md`
4. Archive items > 90 days old to `memory/archive/` (never hard delete per D9)
5. Rewrite `memory/index.md` summaries
6. Refresh `memory/hot.md` from last 3 session entries in `memory/patterns/PATTERNS.jsonl` (≤500 words per §0)

### LINT (on demand)
1. Check format compliance on all wiki pages
2. Report broken cross-references
3. Report orphaned domains (in `memory/index.md` but no page)

## Safety

- All writes via `memory-keeper`
- Archive moves are non-destructive (copy + mark superseded, never delete per D9)
- Respect `PRIVACY.md` mode on every consolidation rewrite
