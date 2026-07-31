"""Versioned SQLite migration runner (stdlib only, vNext ADR-0001).

Contract:
- Each migration is a module ``m####_slug`` under this package, exposing
  ``up(conn: sqlite3.Connection) -> None``.
- ``schema_version`` table records applied numbers with a UTC timestamp.
- ``migrate()`` applies pending migrations in numeric order, transactionally,
  idempotently (double-apply is a no-op).
- Migrations are additive: they must NOT drop or rewrite prior tables.

Used by :class:`shiroe.storage.state.StateDB`.
"""

from __future__ import annotations

import importlib
import pkgutil
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

_MIGRATION_RE = re.compile(r"^m(\d{4})_[a-z0-9_]+$")


def _discover() -> list[tuple[int, str]]:
    """Return (number, module_name) pairs for every migration in the package,
    sorted by number ascending."""
    found: list[tuple[int, str]] = []
    pkg_path = Path(__file__).parent
    for info in pkgutil.iter_modules([str(pkg_path)]):
        m = _MIGRATION_RE.match(info.name)
        if m:
            found.append((int(m.group(1)), info.name))
    found.sort()
    return found


def _ensure_schema_version(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_version (
            number INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            applied_at TEXT NOT NULL
        )
        """
    )


def _applied(conn: sqlite3.Connection) -> set[int]:
    _ensure_schema_version(conn)
    return {row[0] for row in conn.execute("SELECT number FROM schema_version")}


def migrate(conn: sqlite3.Connection) -> list[str]:
    """Apply all pending migrations on ``conn``. Returns names applied."""
    applied = _applied(conn)
    ran: list[str] = []
    for number, name in _discover():
        if number in applied:
            continue
        module = importlib.import_module(f"{__name__}.{name}")
        with conn:  # implicit transaction
            module.up(conn)
            conn.execute(
                "INSERT INTO schema_version(number, name, applied_at) VALUES (?, ?, ?)",
                (number, name, datetime.now(timezone.utc).isoformat(timespec="seconds")),
            )
        ran.append(name)
    return ran


def current_version(conn: sqlite3.Connection) -> int:
    _ensure_schema_version(conn)
    row = conn.execute("SELECT COALESCE(MAX(number), 0) FROM schema_version").fetchone()
    return int(row[0])
