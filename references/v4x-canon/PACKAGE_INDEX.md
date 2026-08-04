# PACKAGE_INDEX.md — Shiroe 4.x Upgrade Package

> **Superseded snapshot.** Retired v4.x canon, archived under
> `references/v4x-canon/**` by `docs/canon/SOURCE_AUTHORITY.md`. It indexes the
> v4.x upgrade package, not what ships today. Current surfaces are listed in
> `README.md` and `shiroe-registry.json`.

> Compiled: May 30, 2026
> Based on: Full Shiroe 4.0 design session (3 conversations, ~8 hours of decisions)
> Session sources: Perplexity AI Shiroe Space

---

## Reading Order for Claude Code

1. INGEST_PROMPT.md — Copy-paste this first. It tells Claude Code exactly what to do.
2. SHIROE_OS.md — Full behavioral constitution. The source of truth for behavior.
3. AGENTS.md — Harness-agnostic source of truth for all tools.
4. CLAUDE.md — One-line stub (See @AGENTS.md).
5. DECISION_LOG.md — All architectural decisions, rationale, and rejected directions.
6. RESEARCH_RESOURCES.md — All links, sources, community data points.
7. MODEL_DEBATE.md — What each AI model needs from Shiroe + ratings table.
8. USE_CASES.md — Six use cases at 110% Shiroe capability.

## Privacy and Config Files (copy to project root)
- PRIVACY.md — Template for every new project
- REDACT.md — Template for every new project
- SHARING_POLICY.md — Template for every new project
- config/BUDGET.md — Token budget configuration

## Memory Structure (copy to project root)
- memory/hot.md — Recent session context (auto-managed)
- memory/MEMORY.md — Agent session notes (auto-managed)
- memory/CONFLICTS.md — Contradiction flags (auto-managed)
- memory/index.md — Domain index (auto-managed)
- memory/patterns/ — Pattern detection log directory
- memory/archive/ — Superseded entries (never deleted)
- skills/drafts/ — Pending skill approvals
- team/ — Team output files

---

## What This Package Does NOT Include

- Bundled MCP tools (see RESEARCH_RESOURCES.md for recommended free stack)
- Hosted service configuration (Shiroe has no hosted service)
- Claude-specific syntax that breaks other harnesses
- Ruflo, LLM Council, CEO persona, or Skill Fleet references (all removed in v4.0)

---

## Key Decisions Summary (from DECISION_LOG.md)

| Decision | Choice |
|----------|--------|
| Memory boundary | One wiki per project/repo |
| Schema interview | Conversational chat flow at project setup only |
| Context rot | Shiroe detects, user resolves from flagged list |
| Pattern detection | 48-80hr window, 3x repetition, user-approved skill drafts |
| God Mode | Auto-detected by model, no separate unlock |
| Audience | Developers First > Knowledge Workers > End Users |
| Harness agnosticism | AGENTS.md as source of truth |
| Privacy | Local canonical memory, abstract-only default, all connectors OFF by default |
| Archive policy | Never hard delete, superseded to memory/archive/ |
| Team packs | On-demand only, max 4 agents |
| Connectors | No bundled tools, recommendation-only |

---

## What Shiroe 4.x Is

A harness-agnostic, local-first AI work control plane for developers.
Works across: Claude Code · Codex · Gemini CLI · Antigravity · Cursor · Windsurf · Aider · Amp · Zed · Hermes · Perplexity Computer.
Free to install. No hosted service. Any model. God Mode unlocked by the model the user brings.
