---
description: Show current session state without modifying anything. Read-only. Operates over flat memory/ layout per SHIROE_OS §0.
---

Read-only. Do not write to memory or modify config.

1. Read `config/PROJECT.md` — report project name, privacy mode (from `PRIVACY.md`), model tier (from `config/BUDGET.md`), parent sync status.
2. Read `memory/hot.md` — report 1-line "current context" summary.
3. Read `memory/index.md` — report domain count, last updated.
4. Count entries in `memory/DECISIONS.md`, `memory/OPEN_QUESTIONS.md`, `memory/RISKS.md`, `memory/CONFLICTS.md`.
5. Read tail 10 lines of `memory/patterns/PATTERNS.jsonl` — report event types + counts. Report active team pack (if any) from `memory/MEMORY.md` `## Active team` section.
6. List active permission overrides (in-memory, if any) + connector enablement summary from `SHARING_POLICY.md`.
7. Count pending skill drafts in `skills/drafts/`.
8. Output:
   ```
   == Shiroe Status ==
   Project: <name>
   Privacy: <mode> | Tier: <Free | Standard | Enterprise> | Parent sync: <on|off>
   Active team: <solo | build | research | red | audit | ship>

   Current context (memory/hot.md):
     <1-line summary>

   Wiki:
     Domains: <N>
     Decisions: <N> (recent: <last decision title>)
     Open questions: <N>
     Risks: <N>
     Conflicts: <N> (snoozed: <N>)

   Recent events (last 10):
     <ts> <agent> <event>
     ...

   Pattern candidates pending: <N> (skills/drafts/)
   Connectors enabled: <list or "none">
   Active session overrides: <list or "none">
   ```
