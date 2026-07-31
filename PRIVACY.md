---
mode: abstract                  # exact | abstract | local-only — DEFAULT abstract per SHIROE_OS §4.3
abstract_rules:
  strip_pii: true
  strip_internal_paths: true
  strip_credentials: true
  strip_numbers: false          # set true to redact $/metric values
local_only_blocks:
  - memory/sync/outbound/
  - memory/sync/parent/
connectors_default: off         # per SHIROE_OS §4.3 — all OFF unless enabled in SHARING_POLICY.md
external_transmission: off      # never transmit wiki content externally without explicit per-action approval
---

<!-- privacy-audit: allow-file "Privacy policy DEFINES what gets redacted; documents credential + PII patterns AS the spec content. Every apparent match is a documentation of the class, not a leak." -->

# PRIVACY.md — What must never leave this project

> Canonical privacy policy. Every write to `memory/` and every external transmission passes through `privacy-guardian`. Sourced from package §4 and DECISION_LOG D8.

## Modes

- **exact** — write full detail (only for solo, trusted-local work and only when user explicitly enables per project)
- **abstract** *(default per §4.3)* — `privacy-abstraction` skill rewrites before write (remove names, paths, credentials, optionally numbers)
- **local-only** — block all writes to `memory/sync/outbound/` and `memory/sync/parent/` (no upward propagation)

Set the active mode in the frontmatter above.

## Setup Interview Questions (asked once at project setup, per §4.2)

1. Is this project personal, client, employer, or public?
2. What categories of data are sensitive? (see `REDACT.md` for concrete classes)
3. Should Shiroe store exact facts, abstractions only, or both?
4. Can any connected MCP tool read this project context, or must this wiki remain local-only? (see `SHARING_POLICY.md`)

If user cancels the interview: Shiroe boots in READ-ONLY mode until the schema is complete.

## What never gets written (regardless of mode)

- credentials, API keys, tokens
- contents of files matched by `.gitignore`
- raw clipboard contents (unless explicitly captured to `memory/raw/`)
- entries listed in `REDACT.md` sensitive classes

## Local-First Canonical Rule (§4.4)

- Local markdown files are the canonical memory. Always.
- Notion, Linear, GitHub, Slack are connected surfaces, not source-of-truth memory.
- Switching harnesses requires no reconfiguration of memory because memory is files.

## External Transmission

- Shiroe NEVER transmits wiki content to any external service unless user explicitly approves per action.
- Connector access is governed by `SHARING_POLICY.md`. Default: OFF.
- See `REDACT.md` for what must be stripped before any external output.

## Per-session overrides

Use `/reset-permissions` to clear session overrides and restore defaults from this file.

## Related files

- `REDACT.md` — concrete sensitive classes to strip
- `SHARING_POLICY.md` — per-connector allowlist
- `config/PERMISSIONS.md` — filesystem / network / MCP permissions
