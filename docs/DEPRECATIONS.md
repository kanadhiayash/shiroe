# Deprecations — Shiroe vNext

One-cycle alias map introduced by the vNext architecture reset (2.0.0-alpha.1). Aliases resolve today; removal target is **2.1.0**.

## Alias map

| Old name | New name | Category | Alias removed in |
|---|---|---|---|
| `small` | `lean` | execution-policy | 2.1.0 |
| `medium` | `balanced` | execution-policy | 2.1.0 |
| `enterprise` | `assured` | execution-policy | 2.1.0 |
| `skill-router` | `capability-resolver` | component | 2.1.0 |
| `fleet-activator` | `capability-prober` | component | 2.1.0 |
| `skill-importer` | `capability-manager` | component | 2.1.0 |
| `haiku` | `fast` | reasoning-class | 2.1.0 |
| `sonnet` | `balanced` | reasoning-class | 2.1.0 |
| `opus` | `deep` | reasoning-class | 2.1.0 |

Source of truth: `shiroe/core/deprecations.py` (`DEPRECATED_ALIASES`). This table must stay in sync with that dict — if they drift, the code wins.

## The `resolve_alias` mechanism

`shiroe.core.deprecations.resolve_alias(name)`:

- Looks up `name` in `DEPRECATED_ALIASES`. If not deprecated, returns `name` unchanged.
- If deprecated, emits a `DeprecationWarning` **once per process** (tracked in an in-memory `_warned` set — repeated calls with the same name don't re-warn) pointing at this file and the 2.1.0 removal target.
- Always returns the canonical replacement, never the old name. Callers should route every user-facing or config-facing name through this function rather than hardcoding old-name fallbacks.

This is a warn-and-translate layer, not a hard failure — old configs, scripts, and registry entries referencing pre-2.0 names keep working through 2.0.x.

## Migration guidance

- **Execution policies**: replace `small`/`medium`/`enterprise` with `lean`/`balanced`/`assured` in any policy config, CLI flag, or team-pack profile reference. `enterprise` wording is banned from user-facing policy names going forward per the architecture plan (§9.2) — don't reintroduce it even as a synonym.
- **Component names**: replace `skill-router` → `capability-resolver`, `fleet-activator` → `capability-prober`, `skill-importer` → `capability-manager` in any script, doc, or automation that names these components directly. The renamed components take on a broader lifecycle scope (all capability types, not just skills) — don't treat this as a pure find-and-replace if you're extending behavior, only if you're referencing the name.
- **Model-tier names**: replace `haiku`/`sonnet`/`opus` with the provider-neutral `fast`/`balanced`/`deep` reasoning classes anywhere a task specifies how much reasoning it needs. Concrete provider model ids (e.g. which model `deep` resolves to) now live only under `shiroe/adapters/providers/<provider>.json` — never hardcode a model id in a mission, skill, or config file again.
- **Team-pack file renames are not yet live.** `team-packs/small.md`, `team-packs/medium.md`, and `team-packs/enterprise.md` still exist on disk under their old filenames — the file renames to `lean.md`/`balanced.md`/`assured.md` (and the broader `team-packs/*.md` → `missions/*.yaml` restructure per the architecture plan §5.1) land in the missions PR (PR 6), not this PR. The alias layer above works today for anything that resolves the *name*; it does not move files.

## What is not aliased

- `faang-mangoes-council` has no alias — it is a hard removal, not a rename. See `docs/adr/ADR-0003-council-removal.md`.
