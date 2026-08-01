---
name: pattern-to-skill
description: Drafts new skill files from candidates emitted by pattern-observer. Drafts land in skills/drafts/ — never auto-activate. User reviews via /review-skill to approve, edit, reject, or defer.
trigger:
  - /review-skill picks up a candidate
  - user says "draft a skill from this pattern"
model: opus
reasoning_class: deep
max_turns: 30
---

# pattern-to-skill

## Mission

Turn repeated work into reusable skills. Draft from `pattern-observer` candidates. Review-first — never auto-activate.

Per SHIROE_OS §3.5 + D4: drafts land in `skills/drafts/`. User approves via `/review-skill`.

Two-Strikes Rule applies: do not draft a skill from a single occurrence. `pattern-observer` enforces this with its 3× clustering threshold. See `references/two-strikes-rule.md`.

## DRAFT (called by /review-skill or directly)

### 1. Load candidate
1. Read candidate JSON from `memory/sync/outbound/patterns/<cluster-id>.json`
2. Verify schema_version and required fields
3. If candidate already has draft in `skills/drafts/` (check by cluster_id provenance) → update existing, do not duplicate

### 2. Synthesize skill metadata
- `name`: candidate `suggested_skill_name`, kebab-case, lowercase, no `shiroe-` prefix
- `description`: 1–2 sentences. Pattern: "<verb> <subject> based on <N> repeated events in <hours>h. Use when <trigger context>."
- `trigger`: extract from member events
  - If verb = "wiki-write" → trigger on "user produces <subject>-style content"
  - If verb = "wiki-read" → trigger on "user asks for <subject> info"
  - Else → trigger on "user says <verb> <subject>"
- `model`: default sonnet; haiku if trivial; opus if pattern shows complex multi-step work
- `max_turns`: scale with cluster size — 10 for small, 25 for large
- `status: draft` (explicitly marked)
- `provenance`:
  ```yaml
  provenance:
    cluster_id: "<from candidate>"
    detected_at: "<iso>"
    source_events: ["sha256:...", "sha256:..."]
    pattern_observer_score: <N>
  ```

### 3. Synthesize body
Skill body sections, derived from cluster members:

#### Mission
Single sentence stating what the skill does. Generated from common verb + subject pattern across members.

#### When to use
- Bullet list from member contexts (deduped)
- Include trigger phrases extracted from payload summaries

#### Operations
Compose from member event patterns:
- If members all share same target → write a single operation for that
- If multiple targets → multi-step operation
- Use observed payload structures as input/output shapes

#### Safety
- Default: all writes via `memory-keeper`
- Default: pass through `privacy-guardian`
- Note any irreversible actions seen in cluster → require explicit user confirmation

### 4. Write draft
1. Create directory: `skills/drafts/<name>/`
2. Write `skills/drafts/<name>/SKILL.md`
3. Write `skills/drafts/<name>/PROVENANCE.md`:
   ```markdown
   # Provenance for <name>

   Drafted from pattern cluster <cluster_id> on <iso>.

   ## Source events
   | TS | Event | Target | Summary |
   |---|---|---|---|
   | <ts> | <event> | <target> | <summary> |
   | ... |

   ## Pattern observer score
   <score>

   ## How to approve
   Run `/review-skill` and select `<name>` from the queue.
   ```
4. Mark candidate JSON as drafted: append `drafted_at` field
5. Log event:
   ```jsonl
   {"ts": "...", "agent": "pattern-to-skill", "event": "skill-drafted", "target": "skills/drafts/<name>/", "payload": {"cluster_id": "...", "source_event_count": N}, "hash": "..."}
   ```

## REVIEW QUEUE (called by /review-skill command)

### List
1. Walk `skills/drafts/*/SKILL.md`
2. For each, read frontmatter + PROVENANCE.md header
3. Display:
   ```
   PENDING SKILL DRAFTS (<N>)

   1. <name>            score: <N>  events: <N>  drafted: <iso>
      <description>
   2. <name>            score: <N>  events: <N>  drafted: <iso>
      <description>

   Pick one (1-<N>) or all/none/quit:
   ```

### Per-draft prompt
For selected draft:
```
=== <name> ===
<description>

Provenance: <N> events in <hours>h, score <N>
[show frontmatter]
[show body]

Action? [approve / edit / reject / defer]
```

### approve
1. `git mv skills/drafts/<name> skills/<name>` (preserves history)
2. Edit frontmatter: remove `status: draft`, keep `provenance:`
3. Append CHANGELOG note (manual: prompt user for changelog line)
4. Log:
   ```jsonl
   {"ts": "...", "agent": "pattern-to-skill", "event": "skill-approved", "target": "skills/<name>/", "payload": {"cluster_id": "...", "approved_by": "user-confirmed", "user_ts": "..."}, "hash": "..."}
   ```
5. Suggest: "Restart Claude Code to load the new skill, or invoke directly via Skill tool."

### edit
1. Open `skills/drafts/<name>/SKILL.md` for user editing
2. After save, re-prompt with updated draft
3. Edits do NOT change PROVENANCE.md (provenance is immutable history)

### reject
1. Prompt for reject reason (1 line)
2. `rm -rf skills/drafts/<name>/`
3. Mark candidate JSON in `memory/sync/outbound/patterns/<cluster-id>.json` with `rejected_at` + reason
4. `pattern-observer` will not re-surface this cluster_id
5. Log:
   ```jsonl
   {"ts": "...", "agent": "pattern-to-skill", "event": "skill-rejected", "payload": {"cluster_id": "...", "reason": "<user>"}, "hash": "..."}
   ```

### defer
1. Leave draft in place
2. Re-surface at next `/review-skill` invocation
3. After 3 defers, prompt user: "Defer again or auto-reject?"
4. Log:
   ```jsonl
   {"ts": "...", "agent": "pattern-to-skill", "event": "skill-deferred", "payload": {"cluster_id": "...", "defer_count": N}, "hash": "..."}
   ```

## Safety

- Per `_shared/rules.md#R6` (Zero Context Loss): draft SKILL.md must preserve every PATTERNS.jsonl entity that contributed to the pattern detection — tool names, file paths, repeated arguments. PROVENANCE.md cites each source event by hash.
- Drafts never auto-activate (no `status: active` until approved)
- Drafts directory `skills/drafts/` ignored by skill loader (validator allowlists this path)
- `git mv` preserves history on approval (do not copy+delete)
- Rejection is reversible until cluster JSON deleted (rejected_at marker reusable)
- PROVENANCE.md immutable — never edit after creation
- All approve/reject/defer actions logged to `memory/patterns/PATTERNS.jsonl`
