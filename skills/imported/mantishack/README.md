---
pack: mantishack
mode: reference-only
classification: restricted
source_path: "operator-configured local path"
license: unknown-verify-with-owner
outbound_write: forbidden
foreign_code_containment: pass
imported_at: 2026-07-10
imported_by: audit(shiroe-consistency-audit)
scope: offensive-security-research
---

# mantishack — reference-only import (restricted)

## Origin

mantishack is a user-local offensive-security research harness kept at an operator-configured path outside this repo. Access is scoped to authorized security research, CTF work, and defensive validation only.

## Classification: restricted

Per user's global `CLAUDE.md`: "All security work follows the same GitHub_OS rules (branch from `main`, no direct push, conventional commits, secrets out of code, classification embedded in filenames when restricted)."

Restricted means:

- No mantishack artifact, output, or configuration is written to Shiroe memory in `exact` privacy mode. `abstract` mode required.
- No mantishack output crosses into the tracked repo tree.
- Any mantishack invocation is logged to a **local-only** journal, never `memory/sync/outbound/`.

## Boundary

No source vendored. mantishack is invoked out-of-band from its own local checkout. This directory exists only to document the boundary.

## Audit-scope use in this session

**None.** WS-D (privacy/security) is a passive policy-vs-enforcement audit; it does not exercise offensive tooling. mantishack is registered because the user asked for the full enterprise fleet stood up, not because the audit needs it.

## Forbidden

- Executing mantishack from within this repo's worktree.
- Passing Shiroe memory into mantishack.
- Committing mantishack output into `shiroe`.
- Any offensive test against third-party infrastructure without prior written authorization.

## Pack membership

Previously registered in a persona pack that was retired in 2.0.0-alpha.1; now tracked as an external capability reference only. Not activated by default.
