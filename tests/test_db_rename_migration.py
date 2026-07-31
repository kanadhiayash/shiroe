"""A pre-rebrand database is adopted, not orphaned.

Canonical state moved from memory/state/zeref2.sqlite to shiroe.sqlite. A
rename with no migration would not error -- StateDB would simply open a new
empty database beside the old one, which presents to the operator as total
memory loss rather than as a rename.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from shiroe.storage.state import DB_RELPATH, StateDB, _LEGACY_DB_RELPATH


def _seed_legacy(root: Path) -> None:
    legacy = root / _LEGACY_DB_RELPATH
    legacy.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(legacy)
    conn.execute("CREATE TABLE marker (note TEXT)")
    conn.execute("INSERT INTO marker VALUES ('pre-rebrand state')")
    conn.commit()
    conn.close()


def test_legacy_database_is_adopted(tmp_path: Path) -> None:
    _seed_legacy(tmp_path)
    db = StateDB(tmp_path)

    assert (tmp_path / DB_RELPATH).exists()
    assert not (tmp_path / _LEGACY_DB_RELPATH).exists()

    row = db.connect().execute("SELECT note FROM marker").fetchone()
    assert row[0] == "pre-rebrand state"


def test_existing_new_database_is_never_overwritten(tmp_path: Path) -> None:
    """If both exist the new one is authoritative. The old is left in place
    for the operator to inspect rather than silently clobbered."""
    _seed_legacy(tmp_path)
    new = tmp_path / DB_RELPATH
    new.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(new)
    conn.execute("CREATE TABLE marker (note TEXT)")
    conn.execute("INSERT INTO marker VALUES ('current state')")
    conn.commit()
    conn.close()

    db = StateDB(tmp_path)
    assert (tmp_path / _LEGACY_DB_RELPATH).exists()
    row = db.connect().execute("SELECT note FROM marker").fetchone()
    assert row[0] == "current state"


def test_no_legacy_database_is_a_no_op(tmp_path: Path) -> None:
    db = StateDB(tmp_path)
    db.connect()
    assert (tmp_path / DB_RELPATH).exists()


def test_legacy_workspace_policy_still_loads(tmp_path: Path) -> None:
    """.zeref/policy/deny.json still applies after the rename to .shiroe/.

    These are deny rules. A rename that stopped loading them would not error
    -- the guard would just quietly stop denying, which is the failure mode
    worth a fallback.
    """
    from shiroe.policy.loader import ActionKind, load_policy_stack

    legacy = tmp_path / ".zeref" / "policy"
    legacy.mkdir(parents=True)
    (legacy / "deny.json").write_text('{"deny": ["network"]}', encoding="utf-8")

    names = [layer.name for layer in load_policy_stack(tmp_path, global_root=tmp_path / "none")]
    assert "project-deny" in names


def test_new_workspace_location_is_preferred(tmp_path: Path) -> None:
    from shiroe.policy.loader import ActionKind, load_policy_stack

    for base, rule in ((".zeref", "subprocess"), (".shiroe", "network")):
        d = tmp_path / base / "policy"
        d.mkdir(parents=True)
        (d / "deny.json").write_text(f'{{"deny": ["{rule}"]}}', encoding="utf-8")

    stack = load_policy_stack(tmp_path, global_root=tmp_path / "none")
    deny = next(layer for layer in stack if layer.name == "project-deny")
    assert ActionKind("network") in deny.denies
    assert ActionKind("subprocess") not in deny.denies
