"""Full-context / no-memory baseline.

Ingests every session and, on recall, returns everything ever ingested for
the current task — no ranking, no retrieval, `k` is ignored. This is the arm
that answers "what if we just handed the model the whole conversation and
skipped memory entirely?" Published research shows full-context frequently
beats purpose-built memory products at small-to-medium context lengths, so a
Zeref number is only honest when reported next to this arm (see
`shiroe/release/claim_gate.py`'s `missing_baseline_pair` constraint).
"""

from __future__ import annotations


class FullContextBackend:
    """Implements the harness ingest/recall interface with no retrieval."""

    name = "full_context"

    def __init__(self) -> None:
        self._chunks: list[str] = []

    def reset(self) -> None:
        self._chunks = []

    def ingest(self, chunk_id: str, text: str) -> None:
        self._chunks.append(text)

    def recall(self, query: str, k: int = 5) -> list[str]:
        # `k` intentionally ignored: full-context means the model sees
        # everything ingested for this task, not a top-k slice.
        return list(self._chunks)
