from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path

from shiroe.lineage.high import HIGH_IMPLEMENTATIONS, audit_high
from shiroe.lineage.intake import REQUIRED_COLUMNS


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
                "category": "agents",
                "decision_from_lineage": "test",
                "zrf_adoption": "Adapt",
                "priority": "high" if idx in HIGH_IMPLEMENTATIONS else "medium",
                "council_lens": "Agent Routing Council",
                "why_it_matters_to_ZRF": "test",
                "guardrail": "Do not bloat core.",
                "implementation_route": "test route",
                "next_analysis_question": "What is missing?",
            })


def test_audit_high_covers_all_high_rows_as_optional_boundaries(tmp_path: Path) -> None:
    path = tmp_path / "lineage.csv"
    _write_csv(path)

    result = audit_high(path, strict=True)

    assert result["passed"] is True
    assert result["counts"]["high_rows"] == 21
    assert result["counts"]["implemented"] == 21
    assert result["counts"]["optional_or_gated"] == 21
    assert result["forms"]["optional-adapter"] == 4


def test_lineage_high_cli_reports_json(tmp_path: Path) -> None:
    path = tmp_path / "lineage.csv"
    _write_csv(path)

    result = subprocess.run(
        [sys.executable, "-m", "shiroe.cli", "lineage", "high", "--strict", "--csv", str(path)],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert '"implemented": 21' in result.stdout
