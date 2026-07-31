"""Shared helpers for deterministic benchmark axes."""

from __future__ import annotations

import json
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from shiroe.memory.atom_store import AtomStore
from shiroe.memory.schemas import create_atom


REPO = Path(__file__).resolve().parent.parent


@contextmanager
def temp_memory_root() -> Iterator[Path]:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for directory in [
            "memory",
            "memory/l0_raw",
            "memory/l1_atoms",
            "memory/indexes",
            "memory/views",
            "memory/reports",
            "memory/handoffs",
            "memory/loops",
            "memory/patterns",
        ]:
            (root / directory).mkdir(parents=True, exist_ok=True)
        (root / "REDACT.md").write_text("", encoding="utf-8")
        AtomStore(root).ensure_layout()
        yield root


def add_atom(
    root: Path,
    *,
    atom_type: str = "fact",
    claim: str,
    source: str = "benchmark",
    evidence: str = "A",
    privacy: str = "public-safe",
    status: str = "active",
    source_type: str = "manual",
) -> dict[str, Any]:
    atom = create_atom(
        atom_type=atom_type,
        claim=claim,
        summary=claim,
        source=source,
        source_type=source_type,
        evidence=evidence,
        confidence="high" if evidence in {"A", "B"} else "unknown",
        status=status,
        privacy=privacy,
        provenance="benchmark fixture",
    )
    return AtomStore(root).append(atom)


def axis_result(axis: str, subs: dict[str, tuple[float, str]]) -> dict[str, Any]:
    score = sum(score for score, _ in subs.values()) / len(subs)
    return {
        "axis": axis,
        "score": round(score, 2),
        "sub": {
            key: {"score": round(score, 2), "evidence": evidence}
            for key, (score, evidence) in subs.items()
        },
    }


def print_json_result(result: dict[str, Any]) -> int:
    print(json.dumps(result, indent=2, sort_keys=True))
    if result.get("skipped"):
        # Skipped axes are reported explicitly; they neither pass nor fail.
        return 0
    return 0 if result["score"] >= 9.0 else 1
