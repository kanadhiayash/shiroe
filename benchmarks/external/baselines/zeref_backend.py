"""Zeref retrieval arm — drives the real `zeref.memory` search stack.

Not a re-implementation: each ingested chunk becomes a real validated atom
(`zeref.memory.schemas.create_atom`) written through `AtomStore`, and recall
goes through `zeref.memory.search.search_atoms` — the same function
`zeref recall` and `zeref explain-search` use. Whatever Zeref actually does
in production is what gets measured here, not a benchmark-only stand-in.
"""

from __future__ import annotations

import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from zeref.memory.atom_store import AtomStore
from zeref.memory.schemas import create_atom
from zeref.memory.search import search_atoms

_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


class ZerefBackend:
    """Implements the harness ingest/recall interface with real Zeref atoms."""

    name = "zeref"

    def __init__(self) -> None:
        self._tmp: tempfile.TemporaryDirectory | None = None
        self._chunk_index = 0
        self._new_root()

    def _new_root(self) -> None:
        if self._tmp is not None:
            self._tmp.cleanup()
        self._tmp = tempfile.TemporaryDirectory(prefix="zeref-bench-zeref-")
        self.root = Path(self._tmp.name)
        self.store = AtomStore(self.root)
        self.store.ensure_layout()
        self._chunk_index = 0

    def reset(self) -> None:
        self._new_root()

    def ingest(self, chunk_id: str, text: str) -> None:
        # Strictly increasing synthetic timestamps: keeps atom ids
        # collision-free (id is derived from type+claim+source+created_at)
        # without depending on wall-clock time, so runs stay reproducible.
        self._chunk_index += 1
        created_at = (_EPOCH + timedelta(seconds=self._chunk_index)).isoformat()
        atom = create_atom(
            atom_type="fact",
            claim=text,
            summary=text[:200],
            source=chunk_id,
            source_type="session",
            status="active",
            created_at=created_at,
            privacy="local-only",
            provenance="benchmarks.external.baselines.zeref_backend",
        )
        self.store.append(atom)

    def recall(self, query: str, k: int = 5) -> list[str]:
        result = search_atoms(self.root, query, limit=k, status="active")
        return [match["atom"]["claim"] for match in result["matches"]]
