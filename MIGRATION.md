# Migration — pre-rename workspaces

The project shipped as **Zeref** before the rename to **Shiroe**. This guide is
the operator-facing half of `docs/DEPRECATIONS.md`: that file is the register
(owner, removal version, test per alias), this one spells out the old names and
what to do about each.

Everything below **still works today**. Nothing here is urgent. Each fallback is
removed in **4.0.0** unless the register says otherwise, and the code that reads
the old spelling lives in exactly one module, `shiroe/compat/legacy_identity.py`.

## Environment variables

Old prefix `ZEREF_`, new prefix `SHIROE_`. The new name wins when both are set;
using the old one emits a `DeprecationWarning` naming its replacement.

```sh
# before
export ZEREF_ALLOW_NETWORK=1
# after
export SHIROE_ALLOW_NETWORK=1
```

Environment variables are the one place where a silent drop is genuinely
dangerous: an unset variable falls back to its default, so a network guard would
quietly re-arm and a configured lock timeout would quietly revert. Re-export
under the new prefix wherever you set them — shell profile, CI config, systemd
unit.

`scripts/fetch-benchmark-data.py` reads `ZEREF_BENCHMARK_DATA` the same way;
rename it to `SHIROE_BENCHMARK_DATA`.

## Workspace directory

Old `.zeref/`, new `.shiroe/`. The old location is read only when the new one
has no file at that path, and doing so warns.

```sh
mv .zeref .shiroe          # per project
mv ~/.zeref ~/.shiroe      # global policies
```

These files are deny rules and write scopes. A rename that stopped loading them
would not error — the guard would just quietly stop denying — which is why the
fallback exists rather than a hard cutover.

## Memory store

Three different files, three different fates.

| Old path | What happens |
|---|---|
| `memory/state/zeref2.sqlite` | Renamed to `memory/state/shiroe.sqlite` automatically on first open, once, and only if the new path does not already exist. If both exist the new one is authoritative and the old is left for you to inspect. |
| `memory/state/zeref.sqlite` | **Not renamed.** This is the v1 layout's live filename. Run the importer to copy its rows into the vNext store; the v1 file is read, never renamed and never deleted. |
| `memory/state/backups/zeref2-*.sqlite` | Still found by `shiroe.storage.importer.rollback`. New backups are written as `shiroe-<ts>.sqlite`. |

```sh
python -c "from shiroe.storage.importer import run_import; print(run_import('.', dry_run=True).to_json())"
```

Dry-run first — it emits the same manifest the real run would, with no writes.
Then drop `dry_run` to import for real; a backup is taken before any write and
`shiroe.storage.importer.rollback` restores it.

The v1 file is deliberately **not** renamed. ADR-0001 makes
`memory/state/shiroe.sqlite` the canonical vNext store, so renaming the v1 file
to a Shiroe name would either collide with a different schema or leave two
Shiroe-named databases both claiming to be current state. The real resolution is
store convergence — import the rows, then drop the v1 file — tracked as issue
**#208**, owner **kanadhiayash**.

## Memory index

`memory/indexes/zeref.sqlite` is a cache derived entirely from the JSONL atoms.
`shiroe.memory.indexer.rebuild_index` deletes it and rebuilds under
`memory/indexes/shiroe.sqlite`. Nothing to do.

## Lineage intake CSV

The 64-source lineage intake CSV is local-only and hand-maintained outside this
repository, so nothing here can rename your copy.

- Filename: `ZRF_64_repo_lineage_intake.csv` → `SHIROE_64_repo_lineage_intake.csv`
- Column `zrf_adoption` → `shiroe_adoption`
- Column `why_it_matters_to_ZRF` → `why_it_matters_to_shiroe`

Both spellings load today and warn; only the new names are ever emitted. An
unrecognised header silently drops the column, which is why the fallback exists.

## Product name

Nothing to do. `shiroe.release.claim_gate` matches both product names when it
scans public copy for unevidenced claims, because docs still in flight, archived
reports and third-party copy all say the old name. A gate that stopped matching
"Zeref" would quietly let an overclaim through. This one has no fixed removal
date — it retires when no reachable copy uses the old name.

## Archived surfaces

`CHANGELOG.md`, `docs/adr/`, `docs/archive/`, `docs/plans/`, `docs/audits/`,
`assets/archive/`, `references/v4x-canon/`, `tests/fixtures/legacy/` and this
file keep the old names on purpose. They are records of what shipped under which
name; rewriting them would falsify the record. `scripts/check-active-identity.py`
holds that line — every other surface must read as Shiroe.
