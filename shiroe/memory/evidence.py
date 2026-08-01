"""Deterministic evidence grading for memory atoms and claims."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from shiroe.memory.atom_store import AtomStore


GRADES = ["A", "B", "C", "D", "F", "unverified"]


def grade_claim(claim: str, *, source: str = "", source_type: str = "unknown") -> dict[str, Any]:
    text = claim.lower()
    if not claim.strip():
        grade = "F"
        reason = "empty claim"
    elif source and source_type in {"file", "tool", "git", "manual", "session", "user"}:
        grade = "A" if source_type in {"file", "tool", "git"} else "B"
        reason = f"source provided via {source_type}"
    elif any(marker in text for marker in ("probably", "maybe", "might", "guess")):
        grade = "D"
        reason = "uncertain language without source"
    else:
        grade = "unverified"
        reason = "no source pointer"
    return {"claim": claim, "evidence": grade, "reason": reason}


def audit_evidence(root: Path | str = Path(".")) -> dict[str, Any]:
    atoms = AtomStore(root).load()
    findings = []
    for atom in atoms:
        if atom["evidence"] in {"F", "unverified"} or not atom["source"]:
            findings.append({
                "id": atom["id"],
                "type": atom["type"],
                "claim": atom["claim"],
                "evidence": atom["evidence"],
                "reason": "missing or weak evidence",
            })
    return {"passed": not findings, "findings": findings}
