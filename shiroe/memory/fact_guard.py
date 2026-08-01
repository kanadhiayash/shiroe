"""Fact guard for unsupported or overreaching memory claims."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from shiroe.memory.atom_store import AtomStore


ABSOLUTE_RE = re.compile(r"\b(always|never|guaranteed|best|perfect|10/10|beats)\b", re.I)
BENCHMARK_RE = re.compile(r"\b(benchmark|score|10/10|beats|outperforms)\b", re.I)


def audit_facts(root: Path | str = Path(".")) -> dict[str, Any]:
    findings = []
    for atom in AtomStore(root).load():
        claim = atom["claim"]
        if atom["evidence"] in {"F", "unverified"}:
            findings.append(_finding(atom, "unsupported", "claim lacks evidence"))
        if ABSOLUTE_RE.search(claim) and atom["evidence"] not in {"A", "B"}:
            findings.append(_finding(atom, "absolute-language", "absolute claim needs strong evidence"))
        if BENCHMARK_RE.search(claim) and atom["evidence"] != "A":
            findings.append(_finding(atom, "benchmark-claim", "benchmark claims require direct source evidence"))
    return {"passed": not findings, "findings": findings}


def _finding(atom: dict[str, Any], kind: str, reason: str) -> dict[str, Any]:
    return {
        "id": atom["id"],
        "type": atom["type"],
        "kind": kind,
        "claim": atom["claim"],
        "evidence": atom["evidence"],
        "reason": reason,
    }
