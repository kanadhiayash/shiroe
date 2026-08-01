"""EvidenceGuard: evidence quality checks for memory cards and docs."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

from shiroe.core.schema import EVIDENCE_GRADES, SOURCE_OPTIONAL_TYPES, MemoryCard
from shiroe.memory_state import MemoryStore


GRADE_DESCRIPTIONS = {
    "A": "Direct primary source, exact, current",
    "B": "Repo file, project doc, or user-confirmed source",
    "C": "User-provided claim, not independently verified",
    "D": "Model inference from partial context",
    "F": "Unsupported, contradicted, or unsafe",
}


@dataclass(frozen=True)
class EvidenceFinding:
    memory_id: str
    severity: str
    reason: str
    fix: str

    def to_dict(self) -> dict:
        return asdict(self)


def grade_text(text: str) -> str:
    lowered = text.lower()
    if any(token in lowered for token in ("source:", "https://", "docs/", "readme.md", "agents.md")):
        return "B"
    if any(token in lowered for token in ("unsupported", "contradicted", "unsafe")):
        return "F"
    if any(token in lowered for token in ("assume", "maybe", "partial context", "inference")):
        return "D"
    return "C"


def check_store(store: MemoryStore) -> list[EvidenceFinding]:
    findings: list[EvidenceFinding] = []
    for card in store.list_cards(limit=1000):
        findings.extend(check_card(card))
    return findings


def check_card(card: MemoryCard) -> list[EvidenceFinding]:
    findings: list[EvidenceFinding] = []
    if card.evidence_grade not in EVIDENCE_GRADES:
        findings.append(EvidenceFinding(card.id, "high", "invalid evidence grade", "Use A, B, C, D, or F."))
    if card.type not in SOURCE_OPTIONAL_TYPES and not card.source_refs:
        findings.append(EvidenceFinding(card.id, "high", "missing source_refs", "Add at least one source reference."))
    if card.evidence_grade in {"D", "F"}:
        findings.append(EvidenceFinding(card.id, "high", f"low evidence grade {card.evidence_grade}", "Upgrade evidence or mark as unknown/assumption."))
    return findings


def list_by_grade(store: MemoryStore, grade: str) -> list[MemoryCard]:
    return [card for card in store.list_cards(limit=1000) if card.evidence_grade == grade]


def upgrade_evidence(store: MemoryStore, memory_id: str, source: str) -> MemoryCard:
    card = store.get_card(memory_id)
    if card is None:
        raise KeyError(f"memory card {memory_id} not found")
    data = card.to_dict()
    refs = list(dict.fromkeys([*card.source_refs, source]))
    data["source_refs"] = refs
    data["evidence_grade"] = "B"
    updated = MemoryCard.from_dict(data)
    with store._connect() as conn:  # internal helper until card update API grows
        store._replace_card(conn, updated)
        conn.commit()
    store.record_event(event="memory-card-evidence-upgrade", payload={"id": memory_id, "source": source})
    return updated


def report_findings(findings: list[EvidenceFinding]) -> str:
    if not findings:
        return "No EvidenceGuard findings.\n"
    return "\n".join(f"{f.severity.upper()} {f.memory_id} {f.reason} Fix: {f.fix}" for f in findings) + "\n"


def check_public_docs(path: Path) -> list[str]:
    issues: list[str] = []
    files = [path] if path.is_file() else sorted(path.rglob("*.md"))
    for file in files:
        for line in file.read_text(errors="ignore").splitlines():
            lowered = line.lower()
            if ("best-in-class" in lowered or "scores 10/10 on all benchmarks" in lowered) and not _negated_example(lowered):
                issues.append(f"{file}: unsupported public claim")
            if "evidence grade: f" in lowered and not _negated_example(lowered):
                issues.append(f"{file}: grade F public claim")
    return issues


def _negated_example(line: str) -> bool:
    return any(token in line for token in ("avoid", "do not", "without", "unsupported", "forbidden", "blocked", "claims"))
