"""Contradiction detection and explicit resolution.

Detection covers two classes:

1. Antonym flips — same claim template using opposite status words
   ("enabled" vs "disabled").
2. Structured conflicts — two active atoms whose claims share the same
   (entity, attribute) template but disagree on the extracted value:
   dates/times, quantities (with units), status keywords, identity values.
   A structured mismatch is only flagged when the two atoms' valid-time
   intervals overlap (see shiroe.memory.bitemporal.valid_intervals_overlap) —
   non-overlapping intervals mean the value legitimately changed over time
   (an update), not a contradiction.

Conflicts are SURFACED, never auto-resolved: the higher evidence grade is
suggested as winner, but resolution stays human-arbitrated (AGENTS.md).
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from shiroe.lock import MemoryLock, atomic_write
from shiroe.memory.atom_store import AtomStore
from shiroe.memory.bitemporal import valid_intervals_overlap
from shiroe.memory.schemas import create_atom


PAIRS = [
    ("enabled", "disabled"),
    ("true", "false"),
    ("pass", "fail"),
    ("public", "private"),
    ("supported", "unsupported"),
]

# Status vocabulary for structured detection: PAIRS plus common state words.
STATUS_WORDS = {word for pair in PAIRS for word in pair} | {
    "passing", "failing", "active", "inactive", "deprecated",
    "approved", "rejected", "open", "closed", "allowed", "blocked",
    "launched", "cancelled", "paused", "running", "stopped",
}

EVIDENCE_RANK = {"A": 5, "B": 4, "C": 3, "D": 2, "F": 1, "unverified": 0}

_MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10, "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}
_MONTH_RE = "|".join(sorted(_MONTHS, key=len, reverse=True))

_UNIT_ALIASES = {
    "percent": "%", "pct": "%",
    "milliseconds": "ms", "millisecond": "ms",
    "seconds": "s", "second": "s", "secs": "s", "sec": "s",
    "minutes": "min", "minute": "min", "mins": "min",
    "hours": "h", "hour": "h", "hrs": "h", "hr": "h",
    "days": "day", "weeks": "week", "months": "month", "years": "year",
    "thousand": "k", "million": "m", "billion": "b",
    "users": "users", "requests": "req", "req": "req",
    "qps": "qps", "rps": "rps",
    "kb": "kb", "mb": "mb", "gb": "gb", "tb": "tb",
    "usd": "$", "dollars": "$", "eur": "€",
}
_UNIT_RE = "|".join(sorted(set(_UNIT_ALIASES) | {"%", "ms", "s", "min", "h", "k", "m", "b", "x"}, key=len, reverse=True))


def scan_contradictions(root: Path | str = Path(".")) -> dict[str, Any]:
    store = AtomStore(root)
    atoms = [atom for atom in store.load(status="active") if atom["type"] != "contradiction"]
    existing_claims = {atom["claim"] for atom in store.load(atom_type="contradiction")}
    created = []
    for index, left in enumerate(atoms):
        for right in atoms[index + 1:]:
            conflict = detect_conflict(left, right)
            if conflict is None:
                continue
            claim = f"Contradiction between {left['id']} and {right['id']}"
            if claim in existing_claims:
                continue
            winner = suggest_winner(left, right)
            suggestion = (
                f"suggested_winner={winner} (higher evidence grade)"
                if winner else "suggested_winner=none (equal evidence grades)"
            )
            contradiction = create_atom(
                atom_type="contradiction",
                claim=claim,
                summary=(
                    f"{left['claim']} <> {right['claim']} | {conflict['reason']} | "
                    f"{suggestion}; human arbitration required"
                ),
                source="shiroe contradictions scan",
                source_type="tool",
                evidence="A",
                confidence="medium",
                status="active",
                links=[
                    {"target_id": left["id"], "relation": "left_claim"},
                    {"target_id": right["id"], "relation": "right_claim"},
                ],
                privacy="private",
                provenance="shiroe-cli contradictions scan",
            )
            created.append(store.append(contradiction))
            existing_claims.add(claim)
    conflicts_md = _write_conflicts_md(Path(root), created) if created else None
    return {"created": created, "count": len(created), "conflicts_md": conflicts_md}


def _write_conflicts_md(root: Path, created: list[dict[str, Any]]) -> str:
    """Surface newly detected contradictions in memory/CONFLICTS.md.

    Uses the ``**Side A/B**`` block format that the conflict parser
    understands, so surfaced conflicts also flow into snapshots.
    """
    memory_dir = root / "memory"
    path = memory_dir / "CONFLICTS.md"
    detected_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    memory_dir.mkdir(parents=True, exist_ok=True)

    # Read-modify-write, so the read belongs inside the lock with the write.
    # Reading first let two detections start from the same base text and each
    # append its own block; the second write then erased the first. A silently
    # dropped contradiction is the one loss this file exists to prevent.
    with MemoryLock(memory_dir):
        existing = path.read_text(encoding="utf-8") if path.exists() else "# Conflicts\n"
        if not existing.strip():
            existing = "# Conflicts\n"
        body = existing.rstrip() + "\n"
        for atom in created:
            if f"## {atom['id']}" in existing:
                continue
            sides = {link.get("relation"): link.get("target_id") for link in atom.get("links", [])}
            body += (
                f"\n## {atom['id']}\n"
                f"**Detected:** {detected_at}\n"
                f"**Side A:** {sides.get('left_claim', '?')}\n"
                f"**Side B:** {sides.get('right_claim', '?')}\n"
                f"**Status:** open\n"
                f"**Summary:** {atom['summary']}\n"
                f"\n---\n"
            )
        atomic_write(path, body)
    return str(path)


def list_contradictions(root: Path | str = Path(".")) -> list[dict[str, Any]]:
    return AtomStore(root).load(atom_type="contradiction")


def show_contradiction(root: Path | str, contradiction_id: str) -> dict[str, Any]:
    atom = AtomStore(root).get(contradiction_id)
    if atom is None or atom["type"] != "contradiction":
        raise KeyError(contradiction_id)
    return atom


def propose_resolution(root: Path | str, contradiction_id: str) -> dict[str, Any]:
    contradiction = show_contradiction(root, contradiction_id)
    store = AtomStore(root)
    linked = [
        atom for atom in (
            store.get(link["target_id"])
            for link in contradiction.get("links", [])
            if isinstance(link, dict) and link.get("target_id")
        ) if atom is not None
    ]
    suggested = suggest_winner(linked[0], linked[1]) if len(linked) == 2 else None
    suggestion_text = (
        f" Suggested winner by evidence grade: {suggested}."
        if suggested else " Evidence grades are equal; no auto-suggestion."
    )
    return {
        "id": contradiction_id,
        "proposal": (
            "User arbitration required. Pick a winner with resolve --winner and provide --reason."
            + suggestion_text
        ),
        "suggested_winner": suggested,
        "linked_claims": contradiction.get("links", []),
    }


def resolve_contradiction(
    root: Path | str,
    contradiction_id: str,
    *,
    winner: str,
    reason: str,
) -> dict[str, Any]:
    if not reason.strip():
        raise ValueError("resolution reason is required")
    store = AtomStore(root)
    contradiction = show_contradiction(root, contradiction_id)
    linked = [link["target_id"] for link in contradiction.get("links", []) if isinstance(link, dict)]
    if winner not in linked:
        raise ValueError("winner must be one of the contradiction linked atom ids")
    superseded = []
    for atom_id in linked:
        if atom_id == winner:
            continue
        superseded.append(store.patch(atom_id, {
            "status": "superseded",
            "provenance": f"superseded by contradiction resolution {contradiction_id}: {reason}",
        }))
    resolved = store.patch(contradiction_id, {
        "status": "archived",
        "summary": f"Resolved winner={winner}. Reason: {reason}",
    })
    return {"resolved": resolved, "winner": winner, "superseded": superseded}


def detect_conflict(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any] | None:
    """Return conflict details when two atoms disagree on a structured value.

    Both claims are reduced to a (entity, attribute) template with typed
    placeholders (<date>, <time>, <qty>, <status>). A collision on the same
    template with different extracted values is a contradiction.
    """
    if not _entities_compatible(left, right):
        return None
    left_template, left_values = _fingerprint(left.get("claim", ""))
    right_template, right_values = _fingerprint(right.get("claim", ""))
    if not left_values or not right_values:
        return None
    if left_template != right_template:
        return None
    if left_values == right_values:
        return None
    if not valid_intervals_overlap(left, right):
        # Same entity/attribute, different value, but non-overlapping valid-time
        # windows: a legitimate update over time (e.g. a price that changed),
        # not a contradiction.
        return None
    kinds = sorted({kind for kind, _ in left_values} | {kind for kind, _ in right_values})
    return {
        "template": left_template,
        "kinds": kinds,
        "left_values": [value for _, value in left_values],
        "right_values": [value for _, value in right_values],
        "reason": (
            f"same entity/field template disagrees on {'/'.join(kinds)} value(s): "
            f"{', '.join(value for _, value in left_values)} vs "
            f"{', '.join(value for _, value in right_values)}"
        ),
    }


def suggest_winner(left: dict[str, Any], right: dict[str, Any]) -> str | None:
    """Suggest the atom with the higher evidence grade. None on a tie.

    Suggestion only — the conflict stays surfaced for human arbitration.
    """
    left_rank = EVIDENCE_RANK.get(left.get("evidence", "unverified"), 0)
    right_rank = EVIDENCE_RANK.get(right.get("evidence", "unverified"), 0)
    if left_rank > right_rank:
        return left["id"]
    if right_rank > left_rank:
        return right["id"]
    return None


def _entities_compatible(left: dict[str, Any], right: dict[str, Any]) -> bool:
    left_names = _entity_names(left)
    right_names = _entity_names(right)
    if not left_names or not right_names:
        return True
    return bool(left_names & right_names)


def _entity_names(atom: dict[str, Any]) -> set[str]:
    names: set[str] = set()
    for entity in atom.get("entities", []) or []:
        name = entity.get("name", "") if isinstance(entity, dict) else str(entity)
        name = str(name).strip().lower()
        if name:
            names.add(name)
    return names


def _fingerprint(text: str) -> tuple[str, list[tuple[str, str]]]:
    """Reduce a claim to (template, extracted values) with typed placeholders."""
    values: list[tuple[str, str]] = []
    lowered = text.lower()

    def _capture(kind: str, normalize):
        def _sub(match: re.Match) -> str:
            values.append((kind, normalize(match)))
            return f"<{kind}>"
        return _sub

    # Dates first so their digits never leak into quantity matching.
    lowered = re.sub(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b",
                     _capture("date", lambda m: f"{int(m[1]):04d}-{int(m[2]):02d}-{int(m[3]):02d}"),
                     lowered)
    lowered = re.sub(rf"\b({_MONTH_RE})\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?(?:,)?\s+(\d{{4}})\b",
                     _capture("date", lambda m: f"{int(m[3]):04d}-{_MONTHS[m[1]]:02d}-{int(m[2]):02d}"),
                     lowered)
    lowered = re.sub(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+(?:of\s+)?({_MONTH_RE})\.?(?:,)?\s+(\d{{4}})\b",
                     _capture("date", lambda m: f"{int(m[3]):04d}-{_MONTHS[m[2]]:02d}-{int(m[1]):02d}"),
                     lowered)
    lowered = re.sub(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b",
                     _capture("date", lambda m: f"{int(m[3]):04d}-{int(m[1]):02d}-{int(m[2]):02d}"),
                     lowered)
    lowered = re.sub(r"\b(\d{1,2}):(\d{2})(?::(\d{2}))?\s*(am|pm)?\b",
                     _capture("time", _normalize_time),
                     lowered)
    lowered = re.sub(rf"([$€£]?)\b(\d+(?:,\d{{3}})*(?:\.\d+)?)\s*({_UNIT_RE})?\b",
                     _capture("qty", _normalize_qty),
                     lowered)
    lowered = re.sub(rf"\b({'|'.join(sorted(STATUS_WORDS, key=len, reverse=True))})\b",
                     _capture("status", lambda m: m[1]),
                     lowered)

    template = re.sub(r"[^a-z0-9<>%$€£ ]+", " ", lowered)
    template = re.sub(r"\s+", " ", template).strip()
    return template, values


def _normalize_time(match: re.Match) -> str:
    hour = int(match[1])
    minute = int(match[2])
    second = int(match[3]) if match[3] else 0
    meridiem = match[4] or ""
    if meridiem == "pm" and hour < 12:
        hour += 12
    if meridiem == "am" and hour == 12:
        hour = 0
    return f"{hour:02d}:{minute:02d}:{second:02d}"


def _normalize_qty(match: re.Match) -> str:
    currency = match[1] or ""
    number = match[2].replace(",", "")
    unit = (match[3] or "").strip()
    unit = _UNIT_ALIASES.get(unit, unit)
    return f"{currency}{number}{unit}"


# --- incoming-write conflict detection -------------------------------------
#
# The structured `detect_conflict` above only fires when both claims yield
# typed values (dates, quantities, status words). Two atoms can still
# contradict each other in plain prose — "Use flagship models only for
# critical tasks" vs "Use flagship models for every task" share a subject
# and disagree, with nothing typed to extract. That case was previously
# caught only by the card-based guard, so the rule is ported here rather
# than dropped: same normalized subject, different normalized claim.


def _norm_text(value: str) -> str:
    return " ".join(str(value).lower().strip().rstrip(".").split())


def detect_incoming_conflicts(
    root: Path | str,
    *,
    summary: str,
    claim: str,
) -> list[dict[str, Any]]:
    """Conflicts between an incoming claim and the active atoms already stored.

    Runs both rules: the plain-prose subject match ported from the card guard,
    and the structured value comparison used by `scan_contradictions`. Returns
    a list of conflict dicts; empty means the write is clear.
    """
    from shiroe.memory.atom_store import AtomStore

    incoming = {"claim": claim, "summary": summary, "entities": []}
    conflicts: list[dict[str, Any]] = []
    for existing in AtomStore(root).load(status="active"):
        same_subject = _norm_text(existing.get("summary", "")) == _norm_text(summary)
        differing_claim = _norm_text(existing.get("claim", "")) != _norm_text(claim)
        if same_subject and differing_claim:
            conflicts.append({
                "existing_id": existing["id"],
                "existing_claim": existing.get("claim", ""),
                "incoming_claim": claim,
                "reason": (
                    "an active atom records the same subject with a different claim"
                ),
            })
            continue
        structured = detect_conflict(existing, incoming)
        if structured is not None:
            conflicts.append({
                "existing_id": existing["id"],
                "existing_claim": existing.get("claim", ""),
                "incoming_claim": claim,
                "reason": structured["reason"],
            })
    return conflicts
