---
name: parent-sync
description: Stages approved summaries + decisions in memory/sync/outbound/, pushes to parent's memory/sync/parent/<child-id>/. Preserves provenance. Surfaces parent-side conflicts. Approval required every push.
trigger:
  - approved /stop with parent sync enabled
  - /sync-parent (manual)
model: sonnet
reasoning_class: balanced
max_turns: 25
---

# parent-sync

## Mission

Push approved child-project state up to a parent project. Provenance preserved. Conflicts surface at parent. Push requires explicit user approval every time.

## Pre-flight

1. Read `config/PARENT_SYNC.md`. If `enabled: false` → exit with "Parent sync not configured".
2. Validate `parent_path`:
   - Path exists
   - Contains a flat `memory/` (is a Shiroe v4.3+ project)
   - Writable by current user
3. If `child_id` is null → assign one:
   - Default: basename of current project root
   - Or prompt user for custom id
   - Persist to `config/PARENT_SYNC.md`

## STAGE (called on /stop or /sync-parent)

1. Read `push_content:` list from `config/PARENT_SYNC.md` (default: summary, decisions, risks, open_questions)
2. For each content type:
   - **summary**: read `memory/index.md` + last 3 events from `memory/patterns/PATTERNS.jsonl` → compose 1-page summary
   - **decisions**: read recent entries (last 30 days) from `memory/DECISIONS.md`
   - **risks**: read open-status entries from `memory/RISKS.md`
   - **open_questions**: read all open from `memory/OPEN_QUESTIONS.md`
3. Pass each through `evidence-curator` FILTER_SYNC — keep only grade ≥ medium
4. Pass each through `privacy-guardian` per current privacy mode (`PRIVACY.md`)
   - If mode = `local-only` → REFUSE, exit with "local-only mode blocks parent sync"
5. Write staged content to `memory/sync/outbound/<iso>/`:
   ```
   memory/sync/outbound/2026-05-30T14:23:11Z/
     summary.md
     decisions.md
     risks.md
     open_questions.md
     manifest.json
   ```
6. Generate `manifest.json`:
   ```json
   {
     "schema_version": "1.0",
     "child_id": "...",
     "child_project_name": "...",
     "ts": "ISO-8601",
     "source_events": ["sha256:...", "sha256:..."],
     "privacy_mode": "exact|abstract",
     "content": ["summary", "decisions", "risks", "open_questions"],
     "entry_counts": {"decisions": 5, "risks": 2, "open_questions": 1}
   }
   ```
7. Log: `{"event": "parent-sync-staged", "target": "memory/sync/outbound/<iso>/"}`

## APPROVE

Surface to user:
```
Staged for parent push → <parent_path>/memory/sync/parent/<child-id>/<iso>/

Contents:
  summary.md            (<N> lines)
  decisions.md          (<N> entries, all grade ≥ medium)
  risks.md              (<N> open)
  open_questions.md     (<N> open)

Privacy mode: <mode>
Provenance: <N> source events from this session

Approve push? [yes / no / preview <file>]
```

If `preview <file>` → display contents, re-prompt
If `no` → exit, staged copy remains in `memory/sync/outbound/` for audit
If `yes` → proceed to PUSH

## PUSH (after approval)

1. Compute target: `<parent_path>/memory/sync/parent/<child_id>/<iso>/`
2. Verify target does not already exist (idempotency via iso ts is fine — collision means clock issue)
3. Copy staged files from `memory/sync/outbound/<iso>/` to target
4. Set target files read-only (`chmod 444`) — parent's `memory-keeper` is the only writer in parent project
5. Append push log to `memory/sync/outbound/<iso>/PUSHED.log`:
   ```
   pushed_at: <iso>
   target: <full-path>
   approved_by: user-confirmed
   ```
6. Log: `{"event": "parent-sync-pushed", "target": "<full-target>", "payload": {"manifest_hash": "..."}}`

## PARENT-SIDE INGEST (next /start on parent)

When parent's `/start` runs, parent's `memory-keeper` checks `memory/sync/parent/*/<latest-iso>/`:
1. For each unprocessed push, read manifest
2. For each entry (decision, risk, open question), run conflict detection against parent's wiki state
3. Conflicting entries → append to parent's `memory/CONFLICTS.md` with provenance pointer to child
4. Non-conflicting entries → ingest into parent's wiki with child provenance label:
   ```
   ### <ts> — <decision>
   **Decided**: <claim>
   **Why**: <reason>
   **Evidence**: <grade> (synced from child <child-id>)
   **Provenance**: child push <iso>, source events: <hashes>
   ```
5. Mark processed: add `INGESTED-<parent-ts>.log` next to manifest
6. Surface to parent user on `/start`:
   ```
   Parent sync ingested from <child-id> at <push-ts>:
     <N> decisions merged
     <N> conflicts flagged → see memory/CONFLICTS.md
   ```

## ROLLBACK

If user spots a bad push:
1. Run `parent-sync rollback <push-iso>` (interactive)
2. Removes pushed files from parent's `memory/sync/parent/<child-id>/<iso>/`
3. Removes any ingested entries from parent's wiki (uses provenance pointers)
4. Adds rollback event to parent's event log
5. Original staged copy in child's `memory/sync/outbound/<iso>/` retained for audit

## Safety

- Per `_shared/rules.md#R6` (Zero Context Loss): every fact, named entity, file path, and provenance tag in the staged outbound must survive verbatim into the parent's `memory/sync/parent/<child-id>/`. Re-diff after privacy-abstraction redaction.
- Push requires explicit user approval every time — no auto-push
- Local-only privacy mode blocks all parent sync
- Pushed content is read-only at parent until parent's memory-keeper processes
- Staged copies retained in child's `memory/sync/outbound/` for audit (never auto-deleted)
- Rollback supported — bad pushes recoverable
- Push provenance preserved on every entry (child id, source event hashes)
- Parent-side conflicts never auto-resolved — user arbitrates at parent
