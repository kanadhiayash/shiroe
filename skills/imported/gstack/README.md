---
pack: gstack
mode: reference-only
classification: public
source_path: "~/.claude/skills/graphify/ + gstack global skill registry"
license: unknown-verify-with-owner
outbound_write: forbidden
foreign_code_containment: pass
imported_at: 2026-07-10
imported_by: audit(shiroe-consistency-audit)
---

# gstack — reference-only import

## Origin

gstack is a global-scope skill collection registered on the user's Claude Code harness under `~/.claude/skills/`. Skills include `browse`, `qa`, `review`, `ship`, `land-and-deploy`, `design-*`, `plan-*`, `investigate`, `benchmark`, `document-*`, `learn`, and 30+ others.

## Boundary

This directory contains **no** vendored gstack source. Shiroe invokes gstack skills through the host harness's global skill registry only. gstack skills may **not** write to `memory/`, `shiroe/`, `benchmarks/`, or any Shiroe-canonical surface.

## Why reference-only

- License provenance across gstack skills is unverified.
- Vendoring would leak internal skill authoring conventions into a public repo.
- `benchmarks/foreign_code_containment.py` stays trivially green when nothing is copied.
- gstack's own update cadence is out-of-band from Shiroe's release cycle.

## Allowed use inside Shiroe sessions

- Invocation via user or via a Shiroe command that delegates (e.g. `/browse`, `/review`).
- Read of gstack skill output as untrusted input — subject to the same privacy scrub as any external tool result.

## Forbidden

- Copying gstack skill files into this repo.
- Executing gstack skills that write outside session scratch.
- Passing raw Shiroe memory content to gstack tools without `privacy-abstraction` first.

## Council pack membership

Previously registered in a persona pack that was retired in 2.0.0-alpha.1; now tracked as an external capability reference only (support surface for documentation/runtime-audit work).
