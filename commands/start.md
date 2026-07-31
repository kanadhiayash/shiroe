---
description: Boot a Shiroe session. Runs interview if config/PROJECT.md missing, otherwise restores context from flat memory/ layout per SHIROE_OS §0.
---

If `config/PROJECT.md` does not exist OR `PRIVACY.md` / `REDACT.md` / `SHARING_POLICY.md` are missing at root OR `$ARGUMENTS` includes `--reset`:
1. Invoke `project-setup` skill to run the interview (creates `config/PROJECT.md`, root `PRIVACY.md`, root `REDACT.md`, root `SHARING_POLICY.md`, `config/PERMISSIONS.md`, `config/PARENT_SYNC.md`, `config/BUDGET.md`).
2. After interview completes, prompt user to re-run `/start` to boot the session.
3. If user cancels mid-interview: Shiroe boots in READ-ONLY mode until the schema is complete (per SHIROE_OS §7).

Otherwise (normal boot, reading-order per SHIROE_OS §0):
1. Invoke `sync-coordinator` agent — apply permissions from `config/PERMISSIONS.md` + connector allowlist from `SHARING_POLICY.md`, mount parent if enabled.
2. Invoke `memory-keeper` agent ORIENT operation:
   - Read `config/PROJECT.md`
   - Read `memory/hot.md` FIRST (≤500 words; current context)
   - Read `memory/index.md` if hot is insufficient (domain index)
   - Read `PRIVACY.md` (root) — before any wiki write or tool use
   - Read `REDACT.md` (root) — before any external output
   - Auto-load first 200 lines of `memory/MEMORY.md` (agent-written session notes per §3.4)
   - Tail last 3 entries of `memory/patterns/PATTERNS.jsonl`
3. Invoke `budget-governor` skill — detect Free / Standard / Enterprise tier; report active tier + always-on context size.
4. If `memory/sync/outbound/handoff-*/` exists (newest), invoke `handoff-orchestrator` CONSUME.
5. Report:
   ```
   Project: <name>
   Last session: <iso>
   Active decisions: <count>
   Open questions: <count>
   Conflicts: <count>
   Privacy mode: <mode>
   Model tier: <Free | Standard | Enterprise>
   Always-on context: ~<N> tokens

   What do you want to work on?
   ```
