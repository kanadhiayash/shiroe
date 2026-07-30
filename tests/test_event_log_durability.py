"""
privacy-audit: allow-file "Tests name event-envelope schema fields only; no user data."

Durability of the canonical event log.

Two defects motivated these tests, both of which let an event the caller had
been told was sealed disappear afterwards.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from zeref.storage.events import EventEnvelope, EventLog  # noqa: E402
from zeref.storage.state import StateDB  # noqa: E402


def _envelope(n: int) -> EventEnvelope:
    return EventEnvelope(
        event_type="capability.approved",
        actor="test",
        target=f"cap-{n}",
        payload={"n": n},
    )


def _log(root: Path, conn: sqlite3.Connection) -> EventLog:
    return EventLog(root, mirror_conn=conn)


def test_final_event_survives_connection_close(tmp_path: Path) -> None:
    """The mirror insert must be committed by the writer, not the caller.

    The insert rides the caller's connection, and callers close without
    committing. sqlite3 discards a pending transaction on close, so the last
    event of every session used to vanish from SQLite while surviving in the
    JSONL chain -- the two stores disagreeing by exactly one row.
    """
    db = StateDB(tmp_path)
    conn = db.connect()
    db.migrate()

    log = _log(tmp_path, conn)
    for n in range(3):
        log.append(_envelope(n))
    conn.close()  # no commit, exactly as every caller does

    reopened = StateDB(tmp_path).connect()
    rows = reopened.execute("SELECT COUNT(*) FROM memory_events").fetchone()[0]
    reopened.close()
    assert rows == 3, f"expected 3 mirrored events after close, found {rows}"


def test_jsonl_and_mirror_agree(tmp_path: Path) -> None:
    """Neither store may hold an event the other lacks."""
    db = StateDB(tmp_path)
    conn = db.connect()
    db.migrate()

    log = _log(tmp_path, conn)
    written = [log.append(_envelope(n))["event_id"] for n in range(5)]
    conn.close()

    from_jsonl = [e["event_id"] for e in EventLog(tmp_path).iter_events()]
    reopened = StateDB(tmp_path).connect()
    from_sql = [r[0] for r in reopened.execute("SELECT event_id FROM memory_events")]
    reopened.close()

    assert sorted(from_jsonl) == sorted(written)
    assert sorted(from_sql) == sorted(written)


def test_append_uses_the_fsynced_helper(tmp_path: Path) -> None:
    """The canonical log must not be less durable than the store it replaced.

    A plain buffered write leaves sealed events in the page cache. Asserting
    the fsync'd helper is used is the only check available without staging a
    real power loss.
    """
    import zeref.storage.events as events_mod

    calls: list[Path] = []
    original = events_mod.atomic_append

    def spy(path: Path, content: str) -> None:
        calls.append(path)
        original(path, content)

    events_mod.atomic_append = spy
    try:
        db = StateDB(tmp_path)
        conn = db.connect()
        db.migrate()
        _log(tmp_path, conn).append(_envelope(0))
        conn.close()
    finally:
        events_mod.atomic_append = original

    assert calls, "append() bypassed the fsync'd helper"
    assert calls[0].name == "events.jsonl"


def test_chain_still_verifies(tmp_path: Path) -> None:
    """Durability changes must not disturb the hash chain."""
    db = StateDB(tmp_path)
    conn = db.connect()
    db.migrate()
    log = _log(tmp_path, conn)
    for n in range(4):
        log.append(_envelope(n))
    conn.close()
    EventLog(tmp_path).verify_chain()  # raises HashChainError on any break
