# Memory Model

> Hand a six-month-old project to a new collaborator. Where do they read first? What do they read second? When do they stop? Zeref answers those three questions with files on disk.

## The store invariant

"What is the source of truth?" has one answer. Everything else is derived.

| Layer | Role |
|---|---|
| SQLite | Canonical current state. |
| JSONL | Canonical append-only history. Appended, never rewritten. |
| Markdown | Generated human-readable view. Carries a do-not-edit header. |
| TOON | Optional generated model-input view. |

The Markdown you read in `memory/` is a view, not the record. Editing it by hand edits the projection rather than the source; regeneration overwrites your change. Write through the CLI or a session so the write passes the guards.

Recorded in [`docs/adr/ADR-0001-canonical-store.md`](https://github.com/kanadhiayash/zeref-memory-engine/blob/main/docs/adr/ADR-0001-canonical-store.md).

## Layout

```
memory/
├── hot.md                   read FIRST — current context, kept short
├── index.md                 domain index — read when hot is insufficient
├── MEMORY.md                session notes
├── DECISIONS.md             confirmed decisions with provenance + evidence grade
├── OPEN_QUESTIONS.md        unresolved questions with owners
├── RISKS.md                 identified risks with severity
├── CONFLICTS.md             contradiction queue awaiting arbitration
├── glossary.md              project-specific terms
├── state/                   canonical structured state
├── views/                   generated views
├── audit/                   append-only traces
├── patterns/                append-only event log
├── snapshots/               point-in-time state with manifests
├── archive/                 superseded content — archived, not deleted
├── raw/                     untouched source material
└── sync/
    ├── outbound/            staged updates awaiting approval
    └── parent/              received updates
```

## Boundary-first reading

This is the property that keeps context bounded as a project grows.

1. **First** — read `memory/hot.md`. Current context, deliberately short.
2. **Second** — read `memory/index.md` only if hot is insufficient. Locate the relevant domain row.
3. **Third** — read only the named section of the named page.
4. **Never** — load a full page just to scan it.

The cost of a read tracks the question being asked, not the age or size of the project. A two-year-old project and a two-week-old one cost the same to resume.

The discipline matters more than it looks. Once an agent is allowed to "just load everything," context spend grows with project age, relevance drops as unrelated material crowds the window, and the failure mode is silent — the agent still answers, just worse.

## The guarded write path

Every write flows through the same sequence. No skill writes to `memory/` directly.

```
claim
  ↓ fact_guard            unsupported superlatives, unsourced absolutes
  ↓ evidence_guard        missing or under-graded evidence
  ↓ privacy_guard         redaction per active mode
  ↓ contradiction_guard   conflicts with stored state
  ↓ write_gate            admits only what cleared the above
disk
```

Concurrency is handled by an advisory lock in `shiroe/lock.py`. A second concurrent writer aborts with a clear error rather than interleaving, and writes are atomic, so an interrupted write does not leave a half-written file.

## Contradiction handling

When a new claim conflicts with a stored one:

1. Halt the write.
2. Fingerprint the claim against stored decisions, open questions, and risks.
3. Append both sides, with provenance, to `memory/CONFLICTS.md`.
4. Surface to the user — immediately, or at session end, by their choice.
5. Wait. The user arbitrates.
6. On resolution, record the outcome with both sides' provenance preserved.

Nothing is auto-resolved. Four shortcuts are refused:

| Refused | Why |
|---|---|
| Recency-wins | Newer is not truer. |
| Grade-wins | Better-sourced is not automatically right for this project. |
| Silent-drop | Discards information without a decision being made. |
| Indefinite-snooze | Defers forever, which is a decision in disguise. |

The stored conflict keeps both sides intact, so arbitrating later loses nothing.

## Evidence grading

Two scores, stored separately, never collapsed.

**Evidence quality** grades the source: provenance, directness, recency, authority, corroboration, reproducibility, and known contradictions.

**Review robustness** grades the deliberation: method diversity, independent agreement, recorded dissent, counterarguments considered.

Agreement among reviewers never upgrades weak source evidence to a strong grade. Confidence in a process is not evidence about the world, and merging the two would let the second quietly launder the first.

## The append-only event log

`memory/patterns/` holds an append-only JSONL event log. Each event is a single JSON line carrying a timestamp, the actor, the event type, a target, a payload, and an integrity hash.

The log is never edited in place. Entries are appended; replay reconstructs state. Pattern detection reads it as a stream.

Event types are allowlisted and each carries a required payload shape, validated by `scripts/shiroe-validate.py`. The validator is the source of truth for which events and values are legal — it enforces the allowlist, per-event schema, and value enums, and reports findings rather than silently accepting unknown types.

## Snapshots and archival

Session close copies the memory state to a timestamped snapshot directory with a manifest. Superseded content moves to `archive/` rather than being deleted, so a bad consolidation is recoverable and provenance chains stay intact.

## Sync

For projects that roll up into a parent, the sequence is staged and gated rather than automatic:

1. **Stage** — filter by evidence grade, pass through privacy redaction, write to `sync/outbound/` with a manifest.
2. **Approve** — explicit user confirmation, with a preview of exactly what would leave.
3. **Push** — copy to the parent's inbound directory and log the push.
4. **Ingest** — the parent runs contradiction detection on arriving entries.

`local-only` privacy mode blocks the whole path. Staged content that has not been approved does not move.

## Validation

```bash
python3 scripts/shiroe-validate.py
```

Checks that registered surfaces resolve on disk, that root privacy files are present, that the memory layout is well-formed, and that the event log passes schema lint. Exits non-zero on any finding.

## Related

- [[Architecture]] — guards, adapters, routing
- [[Privacy-Model]] — modes, classes, export policy
- [[Pattern-Detection]] — how the event log becomes a proposal
- [[Glossary]] — canonical terms
