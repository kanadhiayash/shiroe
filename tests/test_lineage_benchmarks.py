from __future__ import annotations

import csv
from pathlib import Path

from benchmarks import (
    adapter_value,
    critical_adoption_coverage,
    foreign_code_containment,
    high_adoption_coverage,
    license_boundary,
    lineage_import_coverage,
    minimality_pressure,
    reference_only_guardrails,
    security_containment,
)
from shiroe.lineage.critical import CRITICAL_IMPLEMENTATIONS
from shiroe.lineage.high import HIGH_IMPLEMENTATIONS
from shiroe.lineage.intake import REQUIRED_COLUMNS
from shiroe.lineage.reference import REFERENCE_IMPLEMENTATIONS


LINEAGE_AXES = [
    lineage_import_coverage,
    foreign_code_containment,
    critical_adoption_coverage,
    high_adoption_coverage,
    reference_only_guardrails,
    adapter_value,
    minimality_pressure,
    security_containment,
    license_boundary,
]


def test_lineage_benchmark_axes_pass(tmp_path: Path, monkeypatch) -> None:
    csv_path = tmp_path / "lineage.csv"
    _write_csv(csv_path)
    monkeypatch.setenv("ZEREF_LINEAGE_INTAKE_CSV", str(csv_path))

    results = [axis.run() for axis in LINEAGE_AXES]

    assert [result["score"] for result in results] == [10.0] * len(LINEAGE_AXES)
    assert {result["axis"] for result in results} == {
        "lineage_import_coverage",
        "foreign_code_containment",
        "critical_adoption_coverage",
        "high_adoption_coverage",
        "reference_only_guardrails",
        "adapter_value",
        "minimality_pressure",
        "security_containment",
        "license_boundary",
    }


def _write_csv(path: Path) -> None:
    duplicate_repos = {
        22: 3,
        30: 6,
        31: 7,
        32: 8,
        29: 13,
    }
    archived_row = 48
    subdir_row = 17
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=REQUIRED_COLUMNS)
        writer.writeheader()
        for row_id in range(1, 65):
            repo_key = duplicate_repos.get(row_id, row_id)
            repo_url = f"https://github.com/owner/repo-{repo_key}"
            if row_id == 2:
                repo_url = "https://example.com/software-2"
            if row_id == archived_row:
                repo_url = "https://github.com/microsoftarchive/promptbench"
            if row_id == subdir_row:
                repo_url = "https://github.com/google-research/google-research/tree/master/scann"
            writer.writerow({
                "id": str(row_id),
                "section": "A",
                "repo_name": f"Repo {row_id}",
                "source_link_raw": repo_url,
                "repo_url": repo_url,
                "owner": "owner",
                "source_type": "concept/article" if row_id == 2 else "repository",
                "category": _category(row_id),
                "decision_from_lineage": "test",
                "zrf_adoption": _adoption(row_id),
                "priority": _priority(row_id),
                "council_lens": _lens(row_id),
                "why_it_matters_to_ZRF": "test",
                "guardrail": "Do not bloat core.",
                "implementation_route": "test route",
                "next_analysis_question": "What is missing?",
            })


def _priority(row_id: int) -> str:
    if row_id in CRITICAL_IMPLEMENTATIONS:
        return "critical"
    if row_id in HIGH_IMPLEMENTATIONS:
        return "high"
    return "medium"


def _adoption(row_id: int) -> str:
    if row_id in REFERENCE_IMPLEMENTATIONS:
        return "Reference only"
    if row_id == 45:
        return "Reject"
    if row_id in {24, 34}:
        return "Monitor then adapter"
    return "Adapt"


def _category(row_id: int) -> str:
    if row_id in {4, 5, 14}:
        return "graph"
    if row_id in {16, 17}:
        return "retrieval"
    if row_id in {21, 35, 46, 48, 49, 50, 53, 54}:
        return "benchmarks"
    if row_id in {33, 34, 36}:
        return "connectors"
    if row_id in {10, 40, 41, 42, 43, 44, 45}:
        return "security"
    if row_id in {56, 57, 58, 59, 60, 61}:
        return "product-design"
    if row_id in {12, 38}:
        return "developer-tools"
    if row_id in {7, 31, 39}:
        return "workflow"
    if row_id in {2, 62, 63, 64}:
        return "architecture-reference"
    if row_id in {6, 8, 9, 23, 24, 25, 26, 27, 28, 30, 32}:
        return "agents"
    return "memory"


def _lens(row_id: int) -> str:
    category = _category(row_id)
    return {
        "architecture-reference": "Architecture Council",
        "agents": "Agent Routing Council",
        "benchmarks": "Benchmark Architect",
        "connectors": "Connector Governance Council",
        "developer-tools": "Minimality Reviewer",
        "graph": "Graph Architect",
        "memory": "Memory Architect",
        "product-design": "Product Quality Council",
        "retrieval": "Retrieval Architect",
        "security": "Security Gate Engineer",
        "workflow": "Release Governor",
    }[category]
