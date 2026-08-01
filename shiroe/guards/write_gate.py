"""Guarded memory proposal and write pipeline."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from shiroe.audit.logger import AuditLogger
from shiroe.core.errors import GuardRejection, ValidationError
from shiroe.core.schema import SOURCE_OPTIONAL_TYPES
from shiroe.memory.contradictions import detect_incoming_conflicts
from shiroe.guards.fact_guard import matched_claim_category
from shiroe.guards.privacy_guard import classify_text
from shiroe.memory.atom_store import AtomStore
from shiroe.memory.schemas import create_atom, utc_now_iso
from shiroe.memory_state import MemoryStore


@dataclass(frozen=True)
class MemoryProposal:
    claim: str
    type: str = "preference"
    title: str = ""
    privacy_class: str = "internal"
    evidence_grade: str = "C"
    source_refs: list[str] | None = None
    confidence: str = "medium"
    tags: list[str] | None = None
    owner: str = "shiroe"

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["source_refs"] = self.source_refs or ["user-input"]
        data["tags"] = self.tags or []
        if not data["title"]:
            data["title"] = _title_from_claim(self.claim)
        return data


def propose_memory(claim: str, *, output: Path) -> dict[str, Any]:
    proposal = MemoryProposal(claim=claim).to_dict()
    output.write_text(json.dumps(proposal, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return proposal


# Card privacy classes are a policy vocabulary; atom privacy values describe
# how far a record may travel. They are not the same axis, so the mapping is
# explicit and errs toward the MORE restrictive atom value — a record that is
# over-restricted is recoverable, one that is under-restricted has already
# leaked. `secret` and `do_not_store` never reach here: _validate_gate
# rejects both before any write happens.
_PRIVACY_CLASS_TO_ATOM = {
    "public": "public-safe",
    "internal": "private",
    "sensitive": "local-only",
}


def proposal_to_atom(proposal: dict[str, Any]) -> dict[str, Any]:
    """Convert a validated memory proposal into a canonical atom.

    Evidence grade and confidence share a vocabulary with the atom schema and
    carry over unchanged — notably, nothing here can *raise* an evidence
    grade. `title` becomes the atom summary, and the source refs become both
    the atom source and its provenance so the original list survives.
    """
    source_refs = [str(ref) for ref in (proposal.get("source_refs") or [])]
    privacy_class = str(proposal.get("privacy_class", "internal"))
    return create_atom(
        atom_type=str(proposal["type"]),
        claim=str(proposal["claim"]),
        summary=str(proposal.get("title") or proposal["claim"]),
        source=source_refs[0] if source_refs else "",
        source_type="manual",
        evidence=str(proposal.get("evidence_grade", "unverified")),
        confidence=str(proposal.get("confidence", "medium")),
        status="active",
        valid_from=proposal.get("valid_from"),
        valid_until=proposal.get("valid_until"),
        # Transaction time: when Shiroe came to believe this. Set explicitly so
        # the atom participates in bi-temporal ranking from the moment it
        # lands (see shiroe.memory.bitemporal).
        recorded_at=utc_now_iso(),
        tags=list(proposal.get("tags") or []),
        privacy=_PRIVACY_CLASS_TO_ATOM.get(privacy_class, "unknown"),
        provenance="; ".join(source_refs),
    )


def write_from_proposal(path: Path, store: MemoryStore) -> dict[str, Any]:
    audit = AuditLogger(store.memory_root)
    try:
        proposal = json.loads(path.read_text(encoding="utf-8"))
        _validate_gate(proposal, store)
        atom = AtomStore(store.memory_root.root).append(proposal_to_atom(proposal))
        store.record_event(
            event="memory-write-accepted",
            payload={"memory_id": atom["id"], "source": str(path)},
        )
        audit.append(
            event_type="memory_write",
            status="accepted",
            reason="accepted guarded write",
            file=str(path),
            memory_id=atom["id"],
            guards_run=["factguard", "evidenceguard", "privacyguard", "contradictionguard"],
        )
        return atom
    except GuardRejection as exc:
        store.record_event(
            event="memory-write-rejected",
            payload={"source": str(path), "guard": exc.guard, "reason": exc.reason, "fix": exc.fix},
        )
        audit.append(
            event_type="guard_failure",
            status="blocked",
            reason=exc.reason,
            file=str(path),
            guards_run=[exc.guard.lower()],
            payload={"fix": exc.fix},
        )
        audit.append(
            event_type="memory_write",
            status="blocked",
            reason=exc.reason,
            file=str(path),
            guards_run=[exc.guard.lower()],
        )
        raise
    except (KeyError, ValidationError, json.JSONDecodeError) as exc:
        rejection = GuardRejection(
            "WriteGate",
            str(exc),
            "Fix the proposal JSON so it includes valid memory-card fields.",
        )
        store.record_event(
            event="memory-write-rejected",
            payload={"source": str(path), "guard": rejection.guard, "reason": rejection.reason, "fix": rejection.fix},
        )
        audit.append(
            event_type="guard_failure",
            status="blocked",
            reason=rejection.reason,
            file=str(path),
            guards_run=[rejection.guard.lower()],
            payload={"fix": rejection.fix},
        )
        audit.append(
            event_type="memory_write",
            status="blocked",
            reason=rejection.reason,
            file=str(path),
            guards_run=[rejection.guard.lower()],
        )
        raise rejection from exc


def _validate_gate(proposal: dict[str, Any], store: MemoryStore) -> None:
    required = ("type", "claim", "privacy_class", "evidence_grade")
    for field in required:
        if not str(proposal.get(field, "")).strip():
            raise GuardRejection(
                "WriteGate",
                f"The memory proposal is missing `{field}`.",
                f"Add `{field}` to the proposal JSON.",
            )

    privacy_class = proposal["privacy_class"]
    if privacy_class in {"secret", "do_not_store"}:
        raise GuardRejection(
            "PrivacyGuard",
            f"privacy_class `{privacy_class}` cannot be stored.",
            "Use a lower-risk abstraction or do not store this memory.",
        )
    privacy = classify_text(str(proposal.get("claim", "")), redact_md_path=store.memory_root.root / "REDACT.md")
    if privacy["privacy_class"] == "secret":
        raise GuardRejection(
            "PrivacyGuard",
            "The memory claim contains credential-shaped or secret material.",
            "Remove the secret and store only a public-safe abstraction.",
        )

    memory_type = proposal["type"]
    source_refs = list(proposal.get("source_refs") or [])
    if memory_type not in SOURCE_OPTIONAL_TYPES and not source_refs:
        raise GuardRejection(
            "EvidenceGuard",
            "The memory claim is factual or decision-like but has no source_refs.",
            "Add at least one source reference or reclassify the memory as assumption or unknown.",
        )

    claim = str(proposal.get("claim", ""))
    # Delegate to FactGuard's own pattern table rather than restating a subset
    # of it here. An inline copy drifts: phrases added to BLOCKED_PATTERNS were
    # rejected by `shiroe fact check` but still accepted by the write gate.
    if matched_claim_category(claim):
        raise GuardRejection(
            "FactGuard",
            "The memory claim uses unsupported success language.",
            "Rewrite the claim as a sourced, bounded statement.",
        )

    title = str(proposal.get("title") or _title_from_claim(claim))
    conflicts = detect_incoming_conflicts(store.memory_root.root, summary=title, claim=claim)
    if conflicts:
        _write_conflicts_md(store, title, conflicts)
        raise GuardRejection(
            "ContradictionGuard",
            "An active memory atom with the same subject already has a different claim.",
            "Resolve or supersede the existing atom before writing this claim.",
        )


def _write_conflicts_md(store: MemoryStore, title: str, conflicts: list[dict[str, Any]]) -> None:
    """Append blocked conflicts to memory/CONFLICTS.md for human arbitration.

    Conflicts are surfaced, never auto-resolved (AGENTS.md). Entries are
    de-duplicated by heading so a repeated blocked write does not grow the
    file without bound.
    """
    path = store.memory_root.layout.memory_dir / "CONFLICTS.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    if not existing.strip():
        existing = "# Conflicts\n"
    known = {line.strip() for line in existing.splitlines() if line.startswith("## ")}
    body = existing.rstrip() + "\n"
    for conflict in conflicts:
        heading = f"## {title} vs {conflict['existing_id']}"
        if heading in known:
            continue
        known.add(heading)
        body += (
            f"\n{heading}\n\n"
            f"- existing ({conflict['existing_id']}): {conflict['existing_claim']}\n"
            f"- incoming: {conflict['incoming_claim']}\n"
            f"- reason: {conflict['reason']}\n"
        )
    path.write_text(body.rstrip() + "\n", encoding="utf-8")


def _title_from_claim(claim: str) -> str:
    words = claim.strip().rstrip(".").split()
    return " ".join(words[:8]) or "memory proposal"
