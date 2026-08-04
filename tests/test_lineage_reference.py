from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path

from shiroe.lineage.intake import REQUIRED_COLUMNS
from shiroe.lineage.reference import REFERENCE_IMPLEMENTATIONS, audit_reference_only


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
                "category": "security",
                "decision_from_lineage": "test",
                "shiroe_adoption": "Reference only" if idx in REFERENCE_IMPLEMENTATIONS else "Adapt",
                "priority": "medium",
                "council_lens": "Security Gate Engineer",
                "why_it_matters_to_shiroe": "test",
                "guardrail": "Do not bloat core.",
                "implementation_route": "test route",
                "next_analysis_question": "What is missing?",
            })


def test_audit_reference_only_keeps_rows_evidence_only(tmp_path: Path) -> None:
    path = tmp_path / "lineage.csv"
    _write_csv(path)

    result = audit_reference_only(path, strict=True)

    assert result["passed"] is True
    assert result["counts"]["reference_only_rows"] == 19
    assert result["counts"]["implemented"] == 19
    assert result["counts"]["evidence_only"] == 19
    assert result["forms"]["security-containment"] == 3


def test_lineage_reference_cli_reports_json(tmp_path: Path) -> None:
    path = tmp_path / "lineage.csv"
    _write_csv(path)

    result = subprocess.run(
        [sys.executable, "-m", "shiroe.cli", "lineage", "reference", "--strict", "--csv", str(path)],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert '"evidence_only": 19' in result.stdout
