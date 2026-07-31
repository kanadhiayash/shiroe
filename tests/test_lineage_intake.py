from __future__ import annotations

import csv
import os
import subprocess
import sys
from pathlib import Path

import pytest

from shiroe.lineage.intake import REQUIRED_COLUMNS, audit_csv, load_rows


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=REQUIRED_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def _row(row_id: int, *, priority: str = "low", adoption: str = "Adapt") -> dict[str, str]:
    return {
        "id": str(row_id),
        "section": "A",
        "repo_name": f"Repo {row_id}",
        "source_link_raw": "owner/repo",
        "repo_url": "https://github.com/owner/repo",
        "owner": "owner",
        "source_type": "repository",
        "category": "memory",
        "decision_from_lineage": "test",
        "zrf_adoption": adoption,
        "priority": priority,
        "council_lens": "Memory Architect",
        "why_it_matters_to_ZRF": "test",
        "guardrail": "Do not bloat core.",
        "implementation_route": "test route",
        "next_analysis_question": "What is missing?",
    }


def test_load_rows_extracts_github_subdirectory(tmp_path: Path) -> None:
    path = tmp_path / "lineage.csv"
    row = _row(1)
    row["repo_url"] = "https://github.com/google-research/google-research/tree/master/scann"
    _write_csv(path, [row])

    rows = load_rows(path)

    assert rows[0].github_repo == "google-research/google-research"
    assert rows[0].subdirectory == "scann"
    assert rows[0].source_kind == "github"


def test_audit_enforces_lineage_counts(tmp_path: Path) -> None:
    path = tmp_path / "lineage.csv"
    rows = []
    for idx in range(1, 65):
        priority = "critical" if idx <= 10 else ("high" if idx <= 31 else "medium")
        adoption = "Reference only" if idx <= 19 else "Adapt"
        rows.append(_row(idx, priority=priority, adoption=adoption))
    _write_csv(path, rows)

    result = audit_csv(path)

    assert result["passed"] is True
    assert result["counts"]["rows"] == 64
    assert result["counts"]["priorities"]["critical"] == 10
    assert result["counts"]["priorities"]["high"] == 21
    assert result["counts"]["adoptions"]["Reference only"] == 19
    assert result["duplicate_sources"] == {"owner/repo": list(range(1, 65))}


def test_lineage_audit_cli_accepts_project_csv() -> None:
    csv_env = os.environ.get("ZEREF_LINEAGE_INTAKE_CSV")
    if not csv_env:
        pytest.skip("Set ZEREF_LINEAGE_INTAKE_CSV to run the local full intake CSV smoke test.")
    csv_path = Path(csv_env)
    result = subprocess.run(
        [sys.executable, "-m", "shiroe.cli", "lineage", "audit", "--csv", str(csv_path)],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert '"rows": 64' in result.stdout
