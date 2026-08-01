"""Memory atom schema validation.

Atoms are small source-backed records stored as JSONL. They intentionally avoid
optional dependencies so they can run anywhere the base CLI runs.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any


ATOM_TYPES = {
    "fact",
    "decision",
    "risk",
    "task",
    "preference",
    "contradiction",
    "source",
    "error",
    "test",
    "event",
    # Types that previously existed only as memory-card kinds. The atom store
    # is the canonical history, so it has to be able to represent every kind
    # of memory the guarded write path accepts. Adding them here keeps the
    # conversion lossless — the alternative was folding each onto a nearby
    # atom type, which would have silently rewritten what the record means.
    "constraint",
    "unknown",
    "assumption",
    "source_claim",
    "route_policy",
    "privacy_rule",
    "handoff",
}

EVIDENCE_VALUES = {"A", "B", "C", "D", "F", "unverified"}
CONFIDENCE_VALUES = {"high", "medium", "low", "unknown"}
STATUS_VALUES = {"active", "stale", "superseded", "disputed", "archived"}
SOURCE_TYPES = {"user", "file", "tool", "session", "git", "manual", "unknown"}
PRIVACY_VALUES = {"public-safe", "private", "local-only", "unknown"}

REQUIRED_FIELDS = (
    "id",
    "type",
    "claim",
    "summary",
    "source",
    "source_type",
    "evidence",
    "confidence",
    "status",
    "created_at",
    "observed_at",
    "last_confirmed_at",
    "valid_from",
    "valid_until",
    "recorded_at",
    "superseded_at",
    "entities",
    "tags",
    "links",
    "privacy",
    "provenance",
)

# Bi-temporal axes (independent — see shiroe/memory/bitemporal.py):
#   valid time:       valid_from / valid_until  — when the fact was true in the world.
#   transaction time:  recorded_at / superseded_at — when Shiroe learned/un-learned it.
# All four are nullable: an open valid_from/valid_until means "unknown bound" (never
# fabricate one), a null superseded_at means "still the current belief".


class AtomValidationError(ValueError):
    """Raised when an atom does not satisfy the schema."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("; ".join(errors))


def utc_now_iso() -> str:
    """Return an ISO-8601 UTC timestamp with second precision."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def make_atom_id(
    atom_type: str,
    claim: str,
    source: str,
    created_at: str,
    provenance: str = "",
) -> str:
    """Build a deterministic atom ID from stable atom identity fields."""
    payload = json.dumps(
        {
            "type": atom_type,
            "claim": claim,
            "source": source,
            "created_at": created_at,
            "provenance": provenance,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    return f"{atom_type}_{digest}"


def create_atom(
    *,
    atom_type: str,
    claim: str,
    summary: str,
    source: str,
    source_type: str = "manual",
    evidence: str = "unverified",
    confidence: str = "unknown",
    status: str = "active",
    created_at: str | None = None,
    observed_at: str | None = None,
    last_confirmed_at: str | None = None,
    valid_from: str | None = None,
    valid_until: str | None = None,
    recorded_at: str | None = None,
    superseded_at: str | None = None,
    superseded_by: str | None = None,
    supersedes: list[Any] | None = None,
    entities: list[Any] | None = None,
    tags: list[Any] | None = None,
    links: list[Any] | None = None,
    privacy: str = "unknown",
    provenance: str = "",
    atom_id: str | None = None,
) -> dict[str, Any]:
    """Create and validate a complete atom dictionary."""
    ts = created_at or utc_now_iso()
    atom = {
        "id": atom_id or make_atom_id(atom_type, claim, source, ts, provenance),
        "type": atom_type,
        "claim": claim,
        "summary": summary,
        "source": source,
        "source_type": source_type,
        "evidence": evidence,
        "confidence": confidence,
        "status": status,
        "created_at": ts,
        "observed_at": observed_at,
        "last_confirmed_at": last_confirmed_at,
        "valid_from": valid_from,
        "valid_until": valid_until,
        # Transaction time defaults to "recorded now" (recorded_at) / "still
        # current" (superseded_at=None) — distinct from created_at so a future
        # bulk-import path can set recorded_at independently of the atom's own
        # created_at without conflating the two axes.
        "recorded_at": recorded_at or ts,
        "superseded_at": superseded_at,
        # Which atom replaced this one. superseded_at alone records
        # *when* a belief was retired but not *by what*, which loses
        # the chain a reader needs to follow history forward.
        "superseded_by": superseded_by,
        # Reverse of superseded_by: the atom ids this one replaces, so
        # the chain is walkable in both directions.
        "supersedes": supersedes or [],
        "entities": entities or [],
        "tags": tags or [],
        "links": links or [],
        "privacy": privacy,
        "provenance": provenance,
    }
    validate_atom(atom)
    return atom


def validate_atom(atom: dict[str, Any]) -> None:
    """Raise AtomValidationError when an atom violates the schema."""
    errors: list[str] = []

    for field in REQUIRED_FIELDS:
        if field not in atom:
            errors.append(f"missing required field: {field}")

    if errors:
        raise AtomValidationError(errors)

    if atom["type"] not in ATOM_TYPES:
        errors.append(f"invalid type: {atom['type']}")
    if atom["source_type"] not in SOURCE_TYPES:
        errors.append(f"invalid source_type: {atom['source_type']}")
    if atom["evidence"] not in EVIDENCE_VALUES:
        errors.append(f"invalid evidence: {atom['evidence']}")
    if atom["confidence"] not in CONFIDENCE_VALUES:
        errors.append(f"invalid confidence: {atom['confidence']}")
    if atom["status"] not in STATUS_VALUES:
        errors.append(f"invalid status: {atom['status']}")
    if atom["privacy"] not in PRIVACY_VALUES:
        errors.append(f"invalid privacy: {atom['privacy']}")

    for field in ("id", "claim", "summary", "source", "created_at", "provenance"):
        if not isinstance(atom[field], str):
            errors.append(f"{field} must be a string")
    if not atom["created_at"]:
        errors.append("created_at must exist")

    for field in ("entities", "tags", "links"):
        if not isinstance(atom[field], list):
            errors.append(f"{field} must be a list")

    for field in (
        "created_at", "observed_at", "last_confirmed_at",
        "valid_from", "valid_until", "recorded_at", "superseded_at",
    ):
        value = atom[field]
        if value is not None and not _is_iso_datetime(value):
            errors.append(f"{field} must be ISO-8601 or null")

    # Optional supersession links — absent on atoms written before the fields
    # existed, which stay valid rather than failing to load.
    if "supersedes" in atom and not isinstance(atom["supersedes"], list):
        errors.append("supersedes must be a list")
    if atom.get("superseded_by") is not None and not isinstance(atom["superseded_by"], str):
        errors.append("superseded_by must be a string or null")

    if errors:
        raise AtomValidationError(errors)


def _is_iso_datetime(value: Any) -> bool:
    if not isinstance(value, str) or not value:
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True
