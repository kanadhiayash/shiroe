<!-- privacy-audit: allow-file "Sharing-policy spec enumerates connector names + example redact classes; no user data." -->
---
# Per-connector sharing allowlist — all OFF by default per SHIROE_OS §4.3 + D8 + D11.
# Shiroe recommends a connector only after detecting repeated manual behavior. User must enable here before use.
defaults:
  read_project_context: false   # may a connector read PROJECT.md, INDEX.md, decisions?
  write_external: false         # may agents push to external surfaces (Notion page, Linear issue) without per-action approval?

connectors:
  github:
    enabled: false
    read_project_context: false
    allowed_surfaces: []         # e.g. [issues, prs, repo_metadata]
    redact_classes: [credentials, pii, internal_paths]
  linear:
    enabled: false
    read_project_context: false
    allowed_surfaces: []
    redact_classes: [credentials, pii, client_data]
  notion:
    enabled: false
    read_project_context: false
    allowed_surfaces: []
    redact_classes: [credentials, pii, client_data, financial]
  duckduckgo:
    enabled: false
    read_project_context: false  # search queries are external — redact before sending
    redact_classes: [pii, internal_paths, client_data, proprietary_code]
  slack:
    enabled: false
    read_project_context: false
    allowed_surfaces: []
    redact_classes: [credentials, pii, client_data]
  playwright:
    enabled: false               # automation reaches external sites
    redact_classes: [credentials, pii]
  context7:
    enabled: false               # library docs lookup — query goes external
    redact_classes: [internal_paths, proprietary_code]
  sequential_thinking:
    enabled: false
  supabase:
    enabled: false               # cloud memory — disabled by default, local is canonical
    redact_classes: [credentials, pii, client_data]
  desktop_commander:
    enabled: false
  firecrawl:
    enabled: false
    redact_classes: [internal_paths]
  provider_refresh:
    enabled: false          # shiroe providers refresh — list-models GET only, no user payload
    read_project_context: false
    allowed_surfaces: [list-models]
    redact_classes: []
---

# SHARING_POLICY.md — What connectors can read and write

> Sourced from package §4.3, §9, DECISION_LOG D8 + D11. All connectors OFF by default.

## Rules

1. **OFF by default.** Every MCP / connector is `enabled: false` until explicitly enabled.
2. **No bundled tools.** Shiroe ships zero connectors. User installs and enables.
3. **Recommendation-only.** Shiroe recommends a connector after detecting repeated manual behavior. Never installs.
4. **Per-action approval for external writes.** Even when `enabled: true`, agents must request approval per write unless `write_external: true` is set.
5. **Redact before send.** Every external transmission runs through `REDACT.md` classes listed in `redact_classes` for that connector.
6. **Read-context is opt-in.** A connector reading project context (PROJECT.md, INDEX.md, decisions) is separately gated by `read_project_context: true`.

## To enable a connector

1. Install the MCP server (Shiroe does not install on your behalf).
2. Open this file. Flip `enabled: false` → `enabled: true` for that connector.
3. Configure `allowed_surfaces` (which APIs/objects the connector may touch).
4. Verify `redact_classes` covers the data shape going out.
5. Optionally set `read_project_context: true` if the connector needs wiki context.
6. Run `/reset-permissions` to reload `sync-coordinator` permission map.

## Recommended Free MCP Stack (per §9)

**Core** — GitHub, Linear, Notion, DuckDuckGo
**Workflow** — Playwright, Context7, Sequential Thinking
**Optional Power** — Supabase, Desktop Commander, Firecrawl

Details: `references/connector-advisory.md`.

## Related

- `PRIVACY.md` — modes and policy
- `REDACT.md` — concrete classes
- `config/PERMISSIONS.md` — filesystem / network / MCP gating
- `references/connector-advisory.md` — recommendation criteria + setup notes
