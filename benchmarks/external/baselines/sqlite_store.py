"""Simple SQLite FTS baseline.

Ingests chunks into an FTS5 (or LIKE-fallback) table and recalls the top-k
matches for a query. A memory system that cannot beat a 40-line SQLite store
has no business claiming benchmark superiority.
"""

from __future__ import annotations

import re
import sqlite3


_TOKEN_RE = re.compile(r"[a-z0-9]+")


class SqliteFtsBackend:
    """Implements the harness ingest/recall interface with SQLite FTS."""

    name = "sqlite_fts"

    def __init__(self, path: str = ":memory:") -> None:
        self.connection = sqlite3.connect(path)
        try:
            self.connection.execute(
                "CREATE VIRTUAL TABLE IF NOT EXISTS chunks USING fts5(chunk_id, body)"
            )
            self.fts = True
        except sqlite3.OperationalError:
            self.connection.execute(
                "CREATE TABLE IF NOT EXISTS chunks (chunk_id TEXT, body TEXT)"
            )
            self.fts = False

    def reset(self) -> None:
        self.connection.execute("DELETE FROM chunks")
        self.connection.commit()

    def ingest(self, chunk_id: str, text: str) -> None:
        self.connection.execute(
            "INSERT INTO chunks (chunk_id, body) VALUES (?, ?)", (chunk_id, text)
        )
        self.connection.commit()

    def recall(self, query: str, k: int = 5) -> list[str]:
        terms = _TOKEN_RE.findall(query.lower())
        if not terms:
            return []
        if self.fts:
            match = " OR ".join(terms)
            rows = self.connection.execute(
                "SELECT body FROM chunks WHERE chunks MATCH ? ORDER BY rank LIMIT ?",
                (match, k),
            ).fetchall()
            return [row[0] for row in rows]
        like_clauses = " + ".join(
            "(CASE WHEN lower(body) LIKE ? THEN 1 ELSE 0 END)" for _ in terms
        )
        rows = self.connection.execute(
            f"SELECT body, ({like_clauses}) AS score FROM chunks "
            "ORDER BY score DESC LIMIT ?",
            [f"%{term}%" for term in terms] + [k],
        ).fetchall()
        return [row[0] for row in rows if row[1] > 0]
