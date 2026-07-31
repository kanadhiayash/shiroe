<!-- privacy-audit: allow-file "Parent sync config schema; parent_path is a documented field, not a value." -->
---
enabled: false
parent_path: null   # absolute path to parent project root
child_id: null      # this project's id within the parent (auto-set on first sync)
push_on:
  - approved_stop
  - manual_sync_parent
push_content:
  - summary
  - decisions
  - risks
  - open_questions
preserve_provenance: true
---

# Parent Sync

Optional. Lets a child project push approved summaries and decisions upward to a parent project's wiki.

## How to enable

1. Set `enabled: true`
2. Set `parent_path` to the parent project's root (must contain its own flat `memory/` per SHIROE_OS §12)
3. On first `/sync-parent`, `parent-sync` skill creates `<parent_path>/memory/sync/parent/<child-id>/`

## What gets pushed

By default: summary, decisions, risks, open questions. Configurable above.

## Contradictions

If a pushed decision conflicts with a parent decision, `parent-sync` writes to parent's `memory/CONFLICTS.md` and surfaces to the user on the next parent `/start`.

## Provenance

Every pushed entry carries: `child_id`, source event ts, source event hash.
