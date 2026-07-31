"""StateDB — thin SQLite wrapper for the vNext canonical state DB.

Path convention: ``<root>/memory/state/zeref2.sqlite`` (separate file from the
legacy ``zeref.sqlite`` so v1 consumers are untouched during the migration
window).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from shiroe.migrations import current_version, migrate


DB_RELPATH = Path("memory") / "state" / "zeref2.sqlite"


class StateDB:
    def __init__(self, root: Path | str):
        self.root = Path(root)
        self.path = self.root / DB_RELPATH
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None

    def connect(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self.path, timeout=5.0)
            self._conn.execute("PRAGMA foreign_keys = ON")
            self._conn.execute("PRAGMA journal_mode = WAL")
            self._conn.execute("PRAGMA busy_timeout = 5000")
        return self._conn

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def migrate(self) -> list[str]:
        conn = self.connect()
        return migrate(conn)

    def schema_version(self) -> int:
        return current_version(self.connect())

    def tables(self) -> list[str]:
        conn = self.connect()
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        return [r[0] for r in rows]

    def __enter__(self) -> "StateDB":
        self.connect()
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
