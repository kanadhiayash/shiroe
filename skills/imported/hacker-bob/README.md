---
pack: hacker-bob
mode: reference-only
classification: restricted
source_path: "operator-configured local path (MCP)"
license: unknown-verify-with-owner
outbound_write: forbidden
foreign_code_containment: pass
imported_at: 2026-07-10
imported_by: audit(shiroe-consistency-audit)
scope: bug-bounty-hunting
---

# hacker-bob — reference-only import (restricted)

## Origin

hacker-bob is a user-local MCP server for bug-bounty hunting, invoked from an operator-configured path outside this repo. Scope is authorized bounty-program engagements only.

## Classification: restricted

- `abstract` privacy mode required for any Shiroe memory touching hacker-bob outputs.
- No hacker-bob artifact crosses into the tracked repo tree.
- All engagements logged to local-only journals bound to the bounty program's rules of engagement.

## Boundary

No source vendored. MCP invoked out-of-band. This directory documents the boundary only.

## Audit-scope use in this session

**None.** Registered for enterprise-fleet completeness.

## Forbidden

- Executing hacker-bob from within this repo's worktree.
- Any target outside a bounty program's declared scope.
- Committing hacker-bob output into `shiroe`.

## Council pack membership

Previously registered in a persona pack that was retired in 2.0.0-alpha.1; now tracked as an external capability reference only. Not activated by default.
