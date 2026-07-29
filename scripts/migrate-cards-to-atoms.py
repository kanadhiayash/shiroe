#!/usr/bin/env python3
"""Copy memory_cards forward into the canonical JSONL atom store.

Dry-run by default: pass --apply to write. This is a COPY, never a move —
card rows are left untouched so the migration can be re-run, inspected, or
abandoned without data loss. Re-running is safe: an atom whose id already
exists is skipped rather than duplicated, because atom ids are a deterministic
digest of the card's own content.

    python3 scripts/migrate-cards-to-atoms.py            # report only
    python3 scripts/migrate-cards-to-atoms.py --apply    # write atoms
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from zeref.guards.write_gate import proposal_to_atom  # noqa: E402
from zeref.memory.atom_store import AtomStore  # noqa: E402
from zeref.memory.schemas import AtomValidationError  # noqa: E402
from zeref.memory_state import MemoryStore  # noqa: E402


def card_to_proposal(card) -> dict:
    """Shape a card like a write-gate proposal so the one conversion function
    in write_gate is reused rather than duplicated here — a second mapping
    would be free to drift from the one the live write path uses.
    """
    return {
        "type": card.type,
        "title": card.title,
        "claim": card.claim,
        "privacy_class": card.privacy_class,
        "evidence_grade": card.evidence_grade,
        "source_refs": list(card.source_refs or []),
        "confidence": card.confidence,
        "tags": list(card.tags or []),
        "valid_from": card.valid_from,
        "valid_until": card.valid_until,
    }


def migrate(root: Path, *, apply: bool) -> int:
    store = MemoryStore.from_root(root)
    atom_store = AtomStore(root)
    existing_ids = {atom["id"] for atom in atom_store.load()}

    cards = store.list_cards(limit=100_000)
    converted, skipped, failed = [], [], []

    for card in cards:
        try:
            atom = proposal_to_atom(card_to_proposal(card))
        except (AtomValidationError, KeyError, ValueError) as exc:
            failed.append((card.id, str(exc)))
            continue
        if atom["id"] in existing_ids:
            skipped.append(card.id)
            continue
        converted.append((card, atom))
        existing_ids.add(atom["id"])

    print(f"cards found:        {len(cards)}")
    print(f"already migrated:   {len(skipped)}")
    print(f"to convert:         {len(converted)}")
    print(f"cannot convert:     {len(failed)}")
    for card_id, reason in failed:
        print(f"  ! {card_id}: {reason}")

    if not apply:
        for card, atom in converted[:20]:
            print(f"  would write {atom['id']}  <- card {card.id} ({card.type})")
        if len(converted) > 20:
            print(f"  ... and {len(converted) - 20} more")
        print("\nDRY RUN — nothing written. Re-run with --apply to migrate.")
        return 1 if failed else 0

    written = 0
    for card, atom in converted:
        try:
            atom_store.append(atom)
            written += 1
        except AtomValidationError as exc:
            failed.append((card.id, str(exc)))
    print(f"\nwrote {written} atom(s). Card rows left untouched.")
    return 1 if failed else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="project root (default: cwd)")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="actually write atoms; without this the script only reports",
    )
    args = parser.parse_args()
    return migrate(Path(args.root).resolve(), apply=args.apply)


if __name__ == "__main__":
    raise SystemExit(main())
