"""Retrieval accuracy axis for atom recall and explain-search."""

from __future__ import annotations

import sys

from benchmarks.helpers import add_atom, axis_result, print_json_result, temp_memory_root
from zeref.memory.indexer import rebuild_index
from zeref.memory.recall import explain_search, recall


def _top_evidence(result: dict, expected_id: str) -> str:
    """Name WHICH atom ranked first, never its generated id.

    Atom ids are random hex. This evidence string is written into
    benchmarks/results.json and docs/BENCHMARK_REPORT.md, both tracked, so
    interpolating an id bakes a fresh value into the worktree on every run
    and no clean-tree gate can ever pass. The axis only asserts that the
    expected atom came back first, so that is what the evidence records.
    """
    matched = result["matched_atoms"]
    if not matched:
        return "top=none"
    return "top=expected-decision" if matched[0]["atom"]["id"] == expected_id else "top=other-atom"


def run() -> dict:
    with temp_memory_root() as root:
        decision = add_atom(
            root,
            atom_type="decision",
            claim="Use SQLite FTS before optional vector search.",
            source="benchmarks/retrieval_accuracy.py",
            source_type="file",
        )
        add_atom(root, atom_type="risk", claim="Do not load full Markdown memory by default.")
        rebuild_index(root)
        indexed = recall(root, "SQLite FTS", atom_type="decision")
        fallback_db = root / "memory" / "indexes" / "zeref.sqlite"
        fallback_db.unlink()
        fallback = recall(root, "SQLite FTS", atom_type="decision")
        explained = explain_search(root, "SQLite FTS", atom_type="decision")

    indexed_ok = indexed["matched_atoms"][0]["atom"]["id"] == decision["id"]
    fallback_ok = fallback["matched_atoms"][0]["atom"]["id"] == decision["id"]
    explain_ok = explained["candidates"][0]["id"] == decision["id"] and "why_selected" in explained["candidates"][0]
    return axis_result("retrieval_accuracy", {
        "sqlite_indexed_recall": (10.0 if indexed_ok else 0.0, _top_evidence(indexed, decision["id"])),
        "jsonl_fallback_recall": (10.0 if fallback_ok else 0.0, _top_evidence(fallback, decision["id"])),
        "explain_search": (10.0 if explain_ok else 0.0, f"candidates={len(explained['candidates'])}"),
    })


if __name__ == "__main__":
    sys.exit(print_json_result(run()))
