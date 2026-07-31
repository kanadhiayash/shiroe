---
pack: ecc
mode: reference-only
classification: public
source_path: "global ecc plugin (agent + skill registry)"
license: unknown-verify-with-owner
outbound_write: forbidden
foreign_code_containment: pass
imported_at: 2026-07-10
imported_by: audit(shiroe-consistency-audit)
---

# ecc — reference-only import

## Origin

ecc is a global-scope Claude Code plugin exposing multi-language reviewers, build resolvers, and orchestration skills (see the `ecc:*` skill namespace and `ecc:*` agent namespace on this harness). Notable surfaces used by this audit:

- `ecc:code-review`, `ecc:security-scan`, `ecc:agent-eval`
- `ecc:python-review`, `ecc:django-review`, `ecc:fastapi-review`
- `agent-skills:code-reviewer`, `agent-skills:security-auditor`
- `mcp__plugin_ecc_github__*` (used for GitHub issue + branch seeding)
- `mcp__plugin_ecc_playwright__*` (unused by this audit)
- `mcp__plugin_ecc_sequential-thinking__*` (unused by this audit)

## Boundary

No source vendored. Shiroe invokes ecc skills and MCP tools only through the host harness. ecc surfaces may **not** write to `memory/` or `shiroe/` canonical paths.

## Allowed use inside Shiroe sessions

- Slash-command invocation of `ecc:*` skills for language-specific review inside audit workstreams.
- `mcp__plugin_ecc_github__*` for **read-only** GitHub calls plus issue creation on `kanadhiayash/shiroe` (per user's Phase 0.4 authorization).
- `agent-skills:security-auditor` as WS-D subagent.

## Forbidden

- Copying ecc plugin source into this repo.
- Invoking `mcp__plugin_ecc_github__push_files` / `create_or_update_file` against `main`.
- Invoking `mcp__plugin_ecc_github__merge_pull_request` under any circumstance in this audit.
- Passing raw memory content to ecc tools without `privacy-abstraction` first.

## Council pack membership

Previously registered in a persona pack that was retired in 2.0.0-alpha.1; now tracked as an external capability reference only (primary MCP surface for the GitHub-side operational tooling).
