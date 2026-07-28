# Harness Translation Map

> Sourced from ZEREF_OS §10 + DECISION_LOG D7. `AGENTS.md` is the source of truth. Per-harness loader files defer to it.

## The principle

Zeref is harness-agnostic. The canonical spec lives in `AGENTS.md` (Linux Foundation hosted open standard, 60k+ repos, 20+ tools natively support it). Every harness-specific config file is a thin pointer to `AGENTS.md`.

## Per-harness load instructions

| Harness | Config File | Load Method | Stub Location |
|---|---|---|---|
| **Claude Code** | `CLAUDE.md` | One-line: `See @AGENTS.md`. Skills surface as `zeref:<name>`. Commands as `/zeref:<command>`. | `CLAUDE.md` |
| **Codex** | `AGENTS.md` | Native AGENTS.md support | — |
| **Cursor** | `.cursor/rules/zeref.mdc` | Cursor rules format pointing to AGENTS.md | `.cursor/rules/zeref.mdc` |
| **Gemini CLI / Antigravity** | `GEMINI.md` → AGENTS.md | Native AGENTS.md support; thin GEMINI.md stub | `GEMINI.md` |
| **Windsurf** | `.windsurfrules` | Windsurf rules format pointing to AGENTS.md | `.windsurfrules` |
| **Aider** | `.aider.conf.yml` + AGENTS.md | Convention-based, opt-in copy from `.aider.conf.yml.example` | `.aider.conf.yml.example` |
| **Hermes** | `AGENTS.md` | Native support | — |
| **Perplexity Computer** | `AGENTS.md` | Via skills read | — |
| **Amp / Zed** | `AGENTS.md` | Native AGENTS.md support | — |

## Adding a new harness

1. Read `AGENTS.md` cover-to-cover.
2. Create the harness's idiomatic config file (`.<harness>rules` or equivalent).
3. Make it a stub: at minimum, point to `AGENTS.md`.
4. If the harness has a specific skill/agent invocation mechanism, capture per-harness quirks in `config/<harness>-overrides.md`.
5. NEVER duplicate `AGENTS.md` content in the new stub — keep `AGENTS.md` as the single source.
6. Update this map.

## Universal pattern

The stub for any harness should be one of these shapes:

**Reference shape** (preferred):
```
See @AGENTS.md
```

**Rules-format shape** (Cursor / Windsurf / Aider):
```
# <harness name> rules pointing at AGENTS.md
Canonical agent spec: AGENTS.md
On session start, load AGENTS.md first.
Per-harness quirks: config/<harness>-overrides.md
```

## What NEVER belongs in a harness stub

- Copies of memory rules (those live in `AGENTS.md`)
- Privacy policy (those live in `PRIVACY.md` / `REDACT.md` / `SHARING_POLICY.md`)
- Skill definitions (those live in `skills/<name>/SKILL.md`)
- Long documentation (anti-pattern §11: "Do NOT stuff AGENTS.md with documentation. Every line costs context every turn." Stubs should be even shorter.)

## Related

- `AGENTS.md` — canonical spec
- `references/v4x-canon/ZEREF_OS.md` §10
- `INSTALL.md` — per-harness install commands
