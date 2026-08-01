"""Naive full-context file-store baseline.

Ingests every session as a plain text file and, on recall, returns chunks
ranked by naive keyword overlap (falling back to full-context order). This is
the weakest honest baseline: any memory system should beat it on token cost,
and must beat it on accuracy to justify itself.
"""

from __future__ import annotations

import re
import tempfile
from pathlib import Path


_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> set[str]:
    return set(_TOKEN_RE.findall(text.lower()))


class PlainFilesBackend:
    """Implements the harness ingest/recall interface with plain files."""

    name = "plain_files"

    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root) if root else Path(tempfile.mkdtemp(prefix="shiroe-bench-plainfiles-"))
        self.root.mkdir(parents=True, exist_ok=True)
        self._chunks: list[tuple[str, str]] = []  # (chunk_id, text)

    def reset(self) -> None:
        self._chunks = []
        for path in self.root.glob("*.txt"):
            path.unlink()

    def ingest(self, chunk_id: str, text: str) -> None:
        safe = re.sub(r"[^A-Za-z0-9._-]", "_", chunk_id)
        (self.root / f"{safe}.txt").write_text(text, encoding="utf-8")
        self._chunks.append((chunk_id, text))

    def recall(self, query: str, k: int = 5) -> list[str]:
        query_tokens = _tokens(query)
        scored = sorted(
            self._chunks,
            key=lambda item: len(query_tokens & _tokens(item[1])),
            reverse=True,
        )
        return [text for _, text in scored[:k]]
