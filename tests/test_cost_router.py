from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from shiroe.memory.cost_router import audit_budgets, route_operation


def test_route_blocks_markdown_rewrite_without_approval() -> None:
    result = route_operation("markdown-rewrite")
    assert result["executor"] == "blocked"
    assert result["ladder_step"] == "markdown-rewrite"


def test_route_duplicate_and_status_change_use_minimal_steps() -> None:
    duplicate = route_operation("memory-add", duplicate=True)
    status = route_operation("patch", status_change=True)

    assert duplicate["ladder_step"] == "link-existing"
    assert status["ladder_step"] == "atom-patch"


def test_route_public_claim_goes_to_flagship_review() -> None:
    result = route_operation("memory-add", public_claim=True)
    assert result["executor"] == "flagship"
    assert result["ladder_step"] == "flagship-review"


def test_cost_audit_reports_oversized_hot_file(tmp_path: Path) -> None:
    memory = tmp_path / "memory"
    memory.mkdir()
    (memory / "hot.md").write_text("word " * 800, encoding="utf-8")

    result = audit_budgets(tmp_path, strict=True)

    assert result["passed"] is False
    assert result["checks"][0]["artifact"] == "hot.md"


def test_cost_cli_route_json(repo_root: Path) -> None:
    result = subprocess.run(
        [
            sys.executable, "-m", "shiroe", "cost", "route",
            "--operation", "memory-add",
            "--text", "Use atom append.",
        ],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["executor"] == "deterministic"
    assert payload["ladder_step"] == "atom-append"
