"""Canonical memory-card schema for guarded Zeref writes."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from shiroe.core.errors import ValidationError


MEMORY_TYPES = {
    "fact",
    "decision",
    "preference",
    "constraint",
    "risk",
    "unknown",
    "assumption",
    "task",
    "source_claim",
    "contradiction",
    "route_policy",
    "privacy_rule",
    "handoff",
}
MEMORY_STATUSES = {"active", "superseded", "disputed", "archived", "rejected", "pending"}
CONFIDENCE_LEVELS = {"low", "medium", "high", "unknown"}
EVIDENCE_GRADES = {"A", "B", "C", "D", "F"}
PRIVACY_CLASSES = {"public", "internal", "sensitive", "secret", "do_not_store"}
SOURCE_OPTIONAL_TYPES = {"unknown", "assumption"}


@dataclass(frozen=True)
class MemoryCard:
    id: str
    type: str
    title: str
    claim: str
    status: str
    confidence: str
    evidence_grade: str
    source_refs: list[str]
    privacy_class: str
    created_at: str
    updated_at: str
    valid_from: str | None = None
    valid_until: str | None = None
    supersedes: list[str] = field(default_factory=list)
    superseded_by: str | None = None
    tags: list[str] = field(default_factory=list)
    owner: str = "shiroe"

    def __post_init__(self) -> None:
        validate_memory_card(self)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MemoryCard":
        return cls(
            id=str(data.get("id", "")),
            type=str(data.get("type", "")),
            title=str(data.get("title", "")),
            claim=str(data.get("claim", "")),
            status=str(data.get("status", "")),
            confidence=str(data.get("confidence", "")),
            evidence_grade=str(data.get("evidence_grade", "")),
            source_refs=list(data.get("source_refs") or []),
            privacy_class=str(data.get("privacy_class", "")),
            created_at=str(data.get("created_at", "")),
            updated_at=str(data.get("updated_at", "")),
            valid_from=data.get("valid_from"),
            valid_until=data.get("valid_until"),
            supersedes=list(data.get("supersedes") or []),
            superseded_by=data.get("superseded_by"),
            tags=list(data.get("tags") or []),
            owner=str(data.get("owner", "shiroe") or "shiroe"),
        )


def create_memory_card(
    *,
    type: str,
    title: str,
    claim: str,
    privacy_class: str,
    evidence_grade: str,
    source_refs: list[str] | None = None,
    confidence: str = "medium",
    status: str = "active",
    valid_from: str | None = None,
    valid_until: str | None = None,
    supersedes: list[str] | None = None,
    superseded_by: str | None = None,
    tags: list[str] | None = None,
    owner: str = "shiroe",
    now: datetime | None = None,
    counter: int = 1,
    id: str | None = None,
) -> MemoryCard:
    timestamp = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    iso = timestamp.isoformat().replace("+00:00", "Z")
    memory_id = id or f"mem_{timestamp.strftime('%Y_%m_%d')}_{counter:04d}"
    return MemoryCard(
        id=memory_id,
        type=type,
        title=title,
        claim=claim,
        status=status,
        confidence=confidence,
        evidence_grade=evidence_grade,
        source_refs=source_refs or [],
        privacy_class=privacy_class,
        created_at=iso,
        updated_at=iso,
        valid_from=valid_from,
        valid_until=valid_until,
        supersedes=supersedes or [],
        superseded_by=superseded_by,
        tags=tags or [],
        owner=owner,
    )


def validate_memory_card(card: MemoryCard) -> None:
    _required(card.id, "id")
    _required(card.type, "type")
    _required(card.title, "title")
    _required(card.claim, "claim")
    _required(card.status, "status")
    _required(card.confidence, "confidence")
    _required(card.evidence_grade, "evidence_grade")
    _required(card.privacy_class, "privacy_class")
    _required(card.created_at, "created_at")
    _required(card.updated_at, "updated_at")

    _enum(card.type, MEMORY_TYPES, "type")
    _enum(card.status, MEMORY_STATUSES, "status")
    _enum(card.confidence, CONFIDENCE_LEVELS, "confidence")
    _enum(card.evidence_grade, EVIDENCE_GRADES, "evidence_grade")
    _enum(card.privacy_class, PRIVACY_CLASSES, "privacy_class")

    if card.type not in SOURCE_OPTIONAL_TYPES and not card.source_refs:
        raise ValidationError("source_refs are required unless type is unknown or assumption")


def _required(value: str | None, field_name: str) -> None:
    if value is None or not str(value).strip():
        raise ValidationError(f"{field_name} is required")


def _enum(value: str, allowed: set[str], field_name: str) -> None:
    if value not in allowed:
        raise ValidationError(f"{field_name} must be one of: {', '.join(sorted(allowed))}")
