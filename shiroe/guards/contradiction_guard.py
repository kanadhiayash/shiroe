"""ContradictionGuard: local conflict detection for memory cards."""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

from shiroe.lock import MemoryLock, atomic_write
from shiroe.memory_state import MemoryStore


@dataclass(frozen=True)
class Conflict:
    id: str
    severity: str
    status: str
    title: str
    existing_id: str
    existing_claim: str
    incoming_id: str
    incoming_claim: str
    reason: str
    created_at: str

    def to_dict(self) -> dict:
        return asdict(self)


def scan_store(store: MemoryStore) -> list[Conflict]:
    cards = store.list_cards(status="active", limit=1000)
    conflicts: list[Conflict] = []
    for index, left in enumerate(cards):
        for right in cards[index + 1:]:
            if _same_title(left.title, right.title) and _different_claim(left.claim, right.claim):
                conflicts.append(
                    _conflict(
                        title=left.title,
                        existing_id=left.id,
                        existing_claim=left.claim,
                        incoming_id=right.id,
                        incoming_claim=right.claim,
                        severity="high",
                        reason="Active memory cards share a title but disagree on the claim.",
                    )
                )
    return conflicts


def detect_incoming_conflicts(store: MemoryStore, *, title: str, claim: str) -> list[Conflict]:
    conflicts: list[Conflict] = []
    for existing in store.list_cards(status="active", limit=1000):
        if _same_title(existing.title, title) and _different_claim(existing.claim, claim):
            conflicts.append(
                _conflict(
                    title=title,
                    existing_id=existing.id,
                    existing_claim=existing.claim,
                    incoming_id="incoming",
                    incoming_claim=claim,
                    severity="high",
                    reason="Incoming memory card conflicts with an active card using the same title.",
                )
            )
    return conflicts


def write_conflicts(store: MemoryStore, conflicts: list[Conflict]) -> None:
    path = store.memory_root.layout.memory_dir / "CONFLICTS.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text(encoding="utf-8") if path.exists() else "# Conflicts\n"
    if not existing.strip():
        existing = "# Conflicts\n"
    body = existing.rstrip() + "\n\n"
    known = {line.strip() for line in existing.splitlines() if line.startswith("## ")}
    for conflict in conflicts:
        heading = f"## {conflict.id}"
        if heading in known:
            continue
        body += (
            f"{heading}\n"
            f"- status: {conflict.status}\n"
            f"- severity: {conflict.severity}\n"
            f"- title: {conflict.title}\n"
            f"- existing: {conflict.existing_id} - {conflict.existing_claim}\n"
            f"- incoming: {conflict.incoming_id} - {conflict.incoming_claim}\n"
            f"- reason: {conflict.reason}\n\n"
        )
    with MemoryLock(store.memory_root.layout.memory_dir):
        atomic_write(path, body)


def list_conflicts(store: MemoryStore) -> list[Conflict]:
    conflicts = scan_store(store)
    if conflicts:
        write_conflicts(store, conflicts)
    return conflicts


def show_conflict(store: MemoryStore, conflict_id: str) -> Conflict | None:
    for conflict in list_conflicts(store):
        if conflict.id == conflict_id:
            return conflict
    return None


def resolve_conflict(store: MemoryStore, conflict_id: str, *, winner: str, reason: str) -> dict:
    conflict = show_conflict(store, conflict_id)
    if conflict is None:
        raise KeyError(f"conflict {conflict_id} not found")
    loser = conflict.incoming_id if winner == conflict.existing_id else conflict.existing_id
    if loser != "incoming":
        store.archive_card(loser)
    store.record_event(
        event="contradiction-resolved",
        payload={"conflict_id": conflict_id, "winner": winner, "reason": reason},
    )
    return {"conflict_id": conflict_id, "winner": winner, "archived": loser, "reason": reason}


def archive_conflict(store: MemoryStore, conflict_id: str) -> dict:
    store.record_event(event="contradiction-archived", payload={"conflict_id": conflict_id})
    return {"conflict_id": conflict_id, "status": "archived"}


def format_conflicts(conflicts: list[Conflict], *, format: str = "text") -> str:
    if format == "json":
        import json

        return json.dumps([conflict.to_dict() for conflict in conflicts], indent=2, sort_keys=True) + "\n"
    if not conflicts:
        return "No ContradictionGuard findings.\n"
    lines = []
    for conflict in conflicts:
        lines.append(
            f"{conflict.severity.upper()} {conflict.id} {conflict.title}: "
            f"{conflict.existing_id} conflicts with {conflict.incoming_id}"
        )
    return "\n".join(lines) + "\n"


def _conflict(
    *,
    title: str,
    existing_id: str,
    existing_claim: str,
    incoming_id: str,
    incoming_claim: str,
    severity: str,
    reason: str,
) -> Conflict:
    created_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    digest = hashlib.sha256(
        f"{title}|{existing_id}|{existing_claim}|{incoming_id}|{incoming_claim}".encode("utf-8")
    ).hexdigest()
    return Conflict(
        id=f"conflict_{digest[:12]}",
        severity=severity,
        status="open",
        title=title,
        existing_id=existing_id,
        existing_claim=existing_claim,
        incoming_id=incoming_id,
        incoming_claim=incoming_claim,
        reason=reason,
        created_at=created_at,
    )


def _same_title(left: str, right: str) -> bool:
    return _norm(left) == _norm(right)


def _different_claim(left: str, right: str) -> bool:
    return _norm(left) != _norm(right)


def _norm(value: str) -> str:
    return " ".join(value.lower().strip().rstrip(".").split())
