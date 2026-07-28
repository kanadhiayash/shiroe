#!/usr/bin/env python3
"""migrate-bitemporal-facts.py — backfill recorded_at/superseded_at on atoms.

Atoms written before bi-temporal fact versioning (recorded_at/superseded_at)
lack those two keys entirely. `validate_atom` requires the keys to be present
(nullable value) going forward, so pre-existing memory/l1_atoms/*.jsonl rows
need a one-time backfill:

  recorded_at    <- existing created_at (never fabricated: the only timestamp
                     we actually have for "when Zeref learned this").
  superseded_at  <- null (unknown supersession history for old rows; a row
                     that was in fact later replaced still has a `status`
                     field of "superseded" from the old model — we do not
                     invent a superseded_at timestamp we were never given).

valid_from / valid_until are left untouched in all cases — no temporal
"valid in the world" data exists for legacy rows and none is fabricated here.

Policy (matches scripts/migrate-v4.2-to-v4.3.py):
  - Dry-run by DEFAULT. Pass --apply to write changes.
  - Idempotent: atoms that already have both keys are left byte-for-byte
    unchanged; re-running after --apply is a no-op.
  - Never destructive: only adds the two missing keys, never removes or
    rewrites any existing field, never drops a row.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ATOM_DIR = ROOT / "memory" / "l1_atoms"


def log(msg: str, dry: bool) -> None:
    prefix = "[DRY] " if dry else "[APPLY] "
    print(prefix + msg)


def migrate_file(path: Path, *, dry: bool) -> tuple[int, int]:
    """Backfill one atoms JSONL file. Returns (rows_total, rows_changed)."""
    if not path.exists():
        return 0, 0
    lines = path.read_text(encoding="utf-8").splitlines()
    out_lines: list[str] = []
    changed = 0
    for line in lines:
        if not line.strip():
            continue
        atom = json.loads(line)
        needs_recorded = "recorded_at" not in atom
        needs_superseded = "superseded_at" not in atom
        if needs_recorded or needs_superseded:
            if needs_recorded:
                atom["recorded_at"] = atom.get("created_at")
            if needs_superseded:
                atom["superseded_at"] = None
            changed += 1
        out_lines.append(json.dumps(atom, sort_keys=True, separators=(",", ":")))
    if changed and not dry:
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text("".join(line + "\n" for line in out_lines), encoding="utf-8")
        tmp.replace(path)
    return len(out_lines), changed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true",
                        help="Actually perform the migration (default is dry-run).")
    parser.add_argument("--atom-dir", default=str(ATOM_DIR),
                        help="Override memory/l1_atoms/ location (mainly for tests).")
    args = parser.parse_args()

    dry = not args.apply
    atom_dir = Path(args.atom_dir)
    print(f"\n=== migrate-bitemporal-facts.py ({'DRY-RUN' if dry else 'APPLY'}) ===")
    print(f"atom dir: {atom_dir}")
    print()

    if not atom_dir.exists():
        print("no memory/l1_atoms/ directory found — nothing to migrate.")
        return 0

    total_rows = 0
    total_changed = 0
    for path in sorted(atom_dir.glob("*.jsonl")):
        rows, changed = migrate_file(path, dry=dry)
        total_rows += rows
        total_changed += changed
        if changed:
            log(f"{path.name}: backfilled {changed}/{rows} row(s)", dry)
        else:
            log(f"{path.name}: {rows} row(s), already migrated", dry)

    print()
    print(f"total rows: {total_rows}, backfilled: {total_changed}")
    if dry:
        print("DRY-RUN complete. Re-run with --apply to perform the migration.")
    else:
        print("Migration complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
