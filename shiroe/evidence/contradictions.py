"""Contradiction detection between claim + source records."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from shiroe.evidence.schema import ContradictionRecord, SourceRecord


class ContradictionError(ValueError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def detect_contradictions(claim: str,
                          sources: list[SourceRecord]) -> list[ContradictionRecord]:
    """Report every pair (a, b) where a.contradicts includes b.id."""
    out: list[ContradictionRecord] = []
    by_id = {s.id: s for s in sources}
    seen: set[tuple[str, str]] = set()
    for src in sources:
        for other_id in src.contradicts:
            other = by_id.get(other_id)
            if other is None:
                continue
            pair = tuple(sorted((src.id, other.id)))
            if pair in seen:
                continue
            seen.add(pair)
            out.append(ContradictionRecord(
                id="con_" + uuid.uuid4().hex[:16],
                side_a=pair[0], side_b=pair[1],
                detected_at=_now(),
                reason=f"claim {claim!r}: {src.id} declares contradiction with {other.id}",
                grades={pair[0]: "unknown", pair[1]: "unknown"},
            ))
    return out
