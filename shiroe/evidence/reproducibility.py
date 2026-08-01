"""Reproducibility tracking."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class ReproducibilityRecord:
    id: str
    claim: str
    source_id: str
    reproduced_by: str
    reproduced_at: str
    ok: bool
    notes: str = ""


def record_reproduction(*, claim: str, source_id: str,
                        reproduced_by: str, ok: bool,
                        notes: str = "") -> ReproducibilityRecord:
    return ReproducibilityRecord(
        id="rep_" + uuid.uuid4().hex[:16],
        claim=claim, source_id=source_id,
        reproduced_by=reproduced_by, reproduced_at=_now(),
        ok=ok, notes=notes,
    )
