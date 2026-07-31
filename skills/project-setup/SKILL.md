---
name: project-setup
description: Conversational interview that populates config/PROJECT.md, root PRIVACY.md + REDACT.md + SHARING_POLICY.md, config/PERMISSIONS.md, config/PARENT_SYNC.md, config/BUDGET.md. Activates on first /start or when any required config is missing.
trigger:
  - first /start (config/PROJECT.md absent — NOT triggered on subsequent /start runs)
  - any required config file missing (PRIVACY.md, REDACT.md, SHARING_POLICY.md, config/PERMISSIONS.md, config/BUDGET.md)
  - "set up project"
  - "initialize project"
  - "configure this project"
  - "missing config"
  - "redo setup"
  - "reset project config" (re-run of setup for existing project)
model: sonnet
reasoning_class: balanced
max_turns: 20
---

# project-setup

## Mission

Convert any user's messy project goal into structured config in one conversation. Conversational, not formal.

If the user cancels mid-interview, Shiroe boots in READ-ONLY mode until the schema is complete (per SHIROE_OS §7).

## Interview

Ask these in natural language flow, not as a numbered form. Order roughly project → privacy → operations.

### Project (§7)
1. What is this project trying to achieve? (1–2 sentences)
2. What decisions will be made here that you need to remember later?
3. Who else will read this wiki — just you, or a team?
4. What does "done" look like for this project?

### Privacy (§4.2 verbatim)
5. Is this project personal, client, employer, or public?
6. What categories of data are sensitive? *(see REDACT.md classes — credentials, PII, internal_paths, client_data, financial, proprietary_code)*
7. Should Shiroe store exact facts, abstractions only, or both? *(maps to PRIVACY.md mode: exact / abstract / local-only — default is **abstract**)*
8. Can any connected MCP tool read this project context, or must this wiki remain local-only? *(maps to SHARING_POLICY.md)*

On question 6, Shiroe says (verbatim per §7):
> "You can describe the shape of the decision without sharing the data. Shiroe will record the structure, not the content."

### Operations
9. Is there a parent project? (for rollup → `config/PARENT_SYNC.md`)
10. What model tier are you using? (Free / Standard / God Mode — auto-detected if possible per `config/BUDGET.md`)
11. What tools / MCP servers are in play? (Recommend leaving OFF; enable per-connector in `SHARING_POLICY.md`.)
12. Anything else memory should hold from day one?

## Output

Write or update these files. Each gets YAML frontmatter from the answers + a markdown body the user can hand-edit later.

| File | Source questions |
|---|---|
| `config/PROJECT.md` | 1–4, 12 |
| `PRIVACY.md` (root) | 5, 7 (mode), 6 (enabled classes mapping) |
| `REDACT.md` (root) | 6 (enable matching classes) |
| `SHARING_POLICY.md` (root) | 8, 11 |
| `config/PERMISSIONS.md` | defaults; ask if user wants overrides |
| `config/PARENT_SYNC.md` | 9 (enabled only if yes) |
| `config/BUDGET.md` | 10 |

After writing, confirm:
> "Wrote config to: `config/PROJECT.md`, root `PRIVACY.md`, `REDACT.md`, `SHARING_POLICY.md`, `config/PERMISSIONS.md`, `config/PARENT_SYNC.md`, `config/BUDGET.md`. Verify they look right. Run `/start` again to boot the session."

## Safety

- All writes go through `memory-keeper` → `privacy-guardian`
- If user declines to answer a question, leave the field empty with a `# TODO` marker — never invent
- If user cancels before privacy questions are answered, Shiroe refuses to boot until they are. Privacy is non-negotiable per §4.
