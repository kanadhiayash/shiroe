"""
The v1 -> v2 migration must be completable, repeatable, and reversible.

Retiring a migration path means proving the whole lifecycle holds, not just
that an import inserts rows: dry run changes nothing, import writes, a rerun
adds nothing, rollback returns the store to its pre-import shape, and the facts
that came across still mean what they meant.

That last clause is the one with teeth. A v1 atom is bi-temporal -- it carries
valid time (`valid_from` / `valid_until`, when the fact was true in the world)
and transaction time (`recorded_at` / `superseded_at`, when Shiroe learned it).
`memory_records` has columns for valid time and a status for supersession. The
importer read neither: it took type, title and claim, JSON-dumped everything
else into `summary`, and left `valid_from` / `valid_until` NULL on every
imported row. So a fact that stopped being true in 2020 arrived looking
currently true, and a superseded belief arrived looking active.

That is not a lossy-but-honest migration. It is a migration that silently
changes what the data claims, which is worse than one that refuses to run.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from shiroe.storage import importer as importer_mod
from shiroe.storage.events import EventLog
from shiroe.storage.state import StateDB


ATOMS = [
    {
        "id": "atom_closed",
        "type": "decision",
        "title": "Closed-interval fact",
        "claim": "This was true only during 2020.",
        "valid_from": "2020-01-01T00:00:00+00:00",
        "valid_until": "2021-01-01T00:00:00+00:00",
        "recorded_at": "2020-01-02T00:00:00+00:00",
    },
    {
        "id": "atom_current",
        "type": "context",
        "title": "Still-current fact",
        "claim": "This is still true.",
        "valid_from": "2022-06-01T00:00:00+00:00",
        "recorded_at": "2022-06-02T00:00:00+00:00",
    },
    {
        "id": "atom_superseded",
        "type": "risk",
        "title": "Belief we later dropped",
        "claim": "We no longer believe this.",
        "recorded_at": "2021-03-01T00:00:00+00:00",
        "superseded_at": "2023-09-01T00:00:00+00:00",
    },
]


def _seed_atoms(root: Path) -> None:
    atom_dir = root / "memory" / "l1_atoms"
    atom_dir.mkdir(parents=True, exist_ok=True)
    (atom_dir / "atoms.jsonl").write_text(
        "\n".join(json.dumps(a, sort_keys=True) for a in ATOMS) + "\n",
        encoding="utf-8",
    )


def _by_title(root: Path) -> dict[str, sqlite3.Row]:
    conn = StateDB(root).connect()
    conn.row_factory = sqlite3.Row
    return {
        row["title"]: row
        for row in conn.execute(
            "SELECT title, status, valid_from, valid_until FROM memory_records"
        ).fetchall()
    }


def _count(root: Path) -> int:
    return StateDB(root).connect().execute(
        "SELECT COUNT(*) FROM memory_records"
    ).fetchone()[0]


def test_valid_time_survives_the_migration(tmp_path: Path) -> None:
    """A fact that stopped being true must not arrive looking current."""
    _seed_atoms(tmp_path)
    importer_mod.run_import(tmp_path, dry_run=False)

    rows = _by_title(tmp_path)

    closed = rows["Closed-interval fact"]
    assert closed["valid_from"] == "2020-01-01T00:00:00+00:00"
    assert closed["valid_until"] == "2021-01-01T00:00:00+00:00", (
        "a closed valid interval was dropped; the fact now reads as current"
    )

    current = rows["Still-current fact"]
    assert current["valid_from"] == "2022-06-01T00:00:00+00:00"
    assert current["valid_until"] is None, (
        "an open bound must stay open -- never fabricate one"
    )


def test_superseded_beliefs_do_not_arrive_active(tmp_path: Path) -> None:
    """Transaction time is the other axis: a dropped belief must say so."""
    _seed_atoms(tmp_path)
    importer_mod.run_import(tmp_path, dry_run=False)

    rows = _by_title(tmp_path)
    assert rows["Belief we later dropped"]["status"] == "superseded"
    assert rows["Still-current fact"]["status"] == "active"


def test_bitemporal_fields_survive_a_replay(tmp_path: Path) -> None:
    """Migration and replay must agree, or a rebuild rewrites history."""
    _seed_atoms(tmp_path)
    importer_mod.run_import(tmp_path, dry_run=False)

    db = StateDB(tmp_path)
    conn = db.connect()
    before = conn.execute(
        "SELECT id, status, valid_from, valid_until FROM memory_records ORDER BY id"
    ).fetchall()
    assert before, "fixture imported nothing"

    EventLog(tmp_path, mirror_conn=conn).replay_into(conn)

    assert conn.execute(
        "SELECT id, status, valid_from, valid_until FROM memory_records ORDER BY id"
    ).fetchall() == before, "bi-temporal fields changed across a rebuild"


def test_full_migration_lifecycle(tmp_path: Path) -> None:
    """Dry run, import, rerun, rollback -- the retirement gate, in order."""
    _seed_atoms(tmp_path)

    dry = importer_mod.run_import(tmp_path, dry_run=True)
    assert dry.records_written == len(ATOMS)
    assert dry.backup_path is None
    assert _count(tmp_path) == 0, "a dry run wrote to the store"

    first = importer_mod.run_import(tmp_path, dry_run=False)
    assert first.records_written == len(ATOMS)
    assert first.backup_path is not None
    assert _count(tmp_path) == len(ATOMS)

    second = importer_mod.run_import(tmp_path, dry_run=False)
    assert second.records_written == 0, "a rerun duplicated records"
    assert second.records_skipped_duplicate >= len(ATOMS)
    assert _count(tmp_path) == len(ATOMS)

    # Rollback restores the most recent backup, so it undoes the *last* import
    # and not the migration as a whole. The rerun above took its own snapshot
    # with all three records already present, so rolling back lands on 3, not 0.
    # Asserting 0 here would be asserting a cumulative undo that does not exist.
    importer_mod.rollback(tmp_path)
    assert _count(tmp_path) == len(ATOMS), (
        "rollback should restore the snapshot taken before the last import"
    )
    assert "memory_records" in set(StateDB(tmp_path).tables()), (
        "rollback restored a pre-migrate snapshot and lost the schema"
    )


def test_rollback_undoes_a_single_import_completely(tmp_path: Path) -> None:
    """Rolling back the first and only import returns an empty store.

    Paired with the lifecycle test above, this pins the actual contract:
    rollback is per-import, not cumulative.
    """
    _seed_atoms(tmp_path)
    importer_mod.run_import(tmp_path, dry_run=False)
    assert _count(tmp_path) == len(ATOMS)

    importer_mod.rollback(tmp_path)
    assert _count(tmp_path) == 0
