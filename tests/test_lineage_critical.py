from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path

from shiroe.lineage.critical import audit_critical
from shiroe.lineage.intake import REQUIRED_COLUMNS
from shiroe.memory.atom_store import AtomStore
from shiroe.memory.graph import build_derived_graph
from shiroe.memory.schemas import create_atom


CRITICAL_IDS = {1, 3, 11, 12, 14, 15, 22, 39, 40, 47}


def _write_csv(path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=REQUIRED_COLUMNS)
        writer.writeheader()
        for idx in range(1, 65):
            writer.writerow({
                "id": str(idx),
                "section": "A",
                "repo_name": f"Repo {idx}",
                "source_link_raw": f"owner/repo-{idx}",
                "repo_url": f"https://github.com/owner/repo-{idx}",
                "owner": "owner",
                "source_type": "repository",
                "category": "memory",
                "decision_from_lineage": "test",
                "zrf_adoption": "Reference only" if idx <= 19 else "Adapt",
                "priority": "critical" if idx in CRITICAL_IDS else ("high" if 20 <= idx <= 40 else "medium"),
                "council_lens": "Memory Architect",
                "why_it_matters_to_ZRF": "test",
                "guardrail": "Do not bloat core.",
                "implementation_route": "test route",
                "next_analysis_question": "What is missing?",
            })


def test_build_derived_graph_is_rebuildable_from_atoms(tmp_path: Path) -> None:
    atom = create_atom(
        atom_type="decision",
        claim="Use derived graph cache",
        summary="Graph is derived from atoms",
        source="tests/lineage",
        evidence="A",
        confidence="high",
        entities=["Zeref"],
        provenance="test",
    )
    AtomStore(tmp_path).append(atom)

    graph = build_derived_graph(tmp_path)

    assert graph["canonical"] is False
    assert graph["source_of_truth"] == "memory/l1_atoms/*.jsonl"
    assert graph["node_count"] == 3
    assert {edge["kind"] for edge in graph["edges"]} == {"mentions", "sourced_by"}


def test_audit_critical_covers_all_critical_rows(tmp_path: Path) -> None:
    path = tmp_path / "lineage.csv"
    _write_csv(path)

    result = audit_critical(path, strict=True)

    assert result["passed"] is True
    assert result["counts"]["critical_rows"] == 10
    assert result["counts"]["implemented"] == 10
    assert all(not finding["foreign_code_imported"] for finding in result["findings"])


def test_lineage_critical_cli_reports_json(tmp_path: Path) -> None:
    path = tmp_path / "lineage.csv"
    _write_csv(path)

    result = subprocess.run(
        [sys.executable, "-m", "shiroe.cli", "lineage", "critical", "--strict", "--csv", str(path)],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert '"implemented": 10' in result.stdout
