<!-- privacy-audit: allow-file "Harness override config with example paths + skill triggers. No user data." -->
---
harness: claude-code
# Claude-specific behavior overrides that diverge from AGENTS.md defaults.
# Keep this file short. Anything universal belongs in AGENTS.md.
overrides:
  skill_invocation: native        # use Claude Code's Skill tool with `shiroe:<name>`
  command_namespace: /shiroe       # slash commands resolve under /shiroe:<command>
  subagent_model_pref:
    memory-keeper: haiku
    project-setup: sonnet
    pattern-to-skill: opus        # only for draft generation
  hook_ordering: native           # rely on Claude Code SessionStart/UserPromptSubmit hooks
---

# Claude Overrides

> Per SHIROE_OS §12 file structure. Claude-Code-specific quirks live here so AGENTS.md stays harness-agnostic.

**Model resolution:** Concrete model ids resolve via `shiroe/adapters/providers/anthropic.json` (reasoning classes: fast/balanced/deep/frontier).

## Model selection

- **memory-keeper** writes use the `fast` class (haiku alias) for cost/speed (high-frequency, low-reasoning).
- **project-setup** uses the `balanced` class (sonnet alias) for the interview (conversational, moderate reasoning).
- **pattern-to-skill** draft generation uses the `deep` class (opus alias) for creative synthesis from event log.

## Skill / command surface

- All Shiroe skills surface as `shiroe:<skill-name>` via Claude Code's Skill tool.
- All Shiroe commands surface as `/shiroe:<command>` in the slash command namespace.
- The `.claude-plugin/plugin.json` manifest binds these.

## Hooks

Shiroe relies on Claude Code's native SessionStart and UserPromptSubmit hooks (not custom watchers) to trigger:
- `/start` boot sequence on session start
- `privacy-guardian` pre-write checks
- `pattern-observer` background scan on every prompt submit

## What does NOT belong here

- Universal protocol (memory model, privacy modes, team packs) → `AGENTS.md`
- Per-project config → `config/PROJECT.md`
- Budget tier → `config/BUDGET.md`
- Connector enablement → `SHARING_POLICY.md`
