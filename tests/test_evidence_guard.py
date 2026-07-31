"""EvidenceGuard tests."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from shiroe.guards.evidence_guard import check_card, check_public_docs, grade_text
from shiroe.memory import scaffold_project
from shiroe.memory_state import MemoryStore


def _env(repo_root: Path) -> dict:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo_root) + os.pathsep + env.get("PYTHONPATH", "")
    return env


def _run(repo_root: Path, cwd: Path, args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "shiroe", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        env=_env(repo_root),
    )


def _store(root: Path) -> MemoryStore:
    (root / "AGENTS.md").write_text("# AGENTS.md\n", encoding="utf-8")
    scaffold_project(root, name="evidence", privacy="abstract", tier="auto", parent="")
    return MemoryStore.from_root(root)


def test_evidence_grade_validation_and_missing_source_detection(tmp_path: Path) -> None:
    store = _store(tmp_path)
    low = store.add_card(
        type="assumption",
        title="low evidence",
        claim="This came from partial context.",
        privacy_class="internal",
        evidence_grade="D",
    )
    findings = check_card(low)
    assert findings
    assert "low evidence grade D" in findings[0].reason


def test_evidence_upgrade_command(repo_root: Path, tmp_path: Path) -> None:
    store = _store(tmp_path)
    card = store.add_card(
        type="assumption",
        title="needs source",
        claim="Linear is the delivery source of truth.",
        privacy_class="internal",
        evidence_grade="C",
    )

    upgraded = _run(repo_root, tmp_path, ["evidence", "upgrade", card.id, "--source", "docs/plans/ZEREF_HARDENING_RECON.md"])
    assert upgraded.returncode == 0, upgraded.stderr
    data = json.loads(upgraded.stdout)
    assert data["evidence_grade"] == "B"
    assert "docs/plans/ZEREF_HARDENING_RECON.md" in data["source_refs"]


def test_evidence_list_and_report(repo_root: Path, tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.add_card(
        type="unknown",
        title="unknown target",
        claim="The deployment target is unknown.",
        privacy_class="internal",
        evidence_grade="D",
    )
    listed = _run(repo_root, tmp_path, ["evidence", "list", "--grade", "D"])
    assert listed.returncode == 0, listed.stderr
    assert json.loads(listed.stdout)[0]["evidence_grade"] == "D"

    report = _run(repo_root, tmp_path, ["evidence", "report"])
    assert report.returncode == 1
    assert "low evidence grade D" in report.stdout


def test_public_docs_with_grade_f_and_claims(tmp_path: Path) -> None:
    doc = tmp_path / "PUBLIC.md"
    doc.write_text("Zeref is best-in-class.\n\nEvidence grade: F\n", encoding="utf-8")
    issues = check_public_docs(doc)
    assert len(issues) == 2


def test_grade_text_heuristic() -> None:
    assert grade_text("Source: README.md") == "B"
    assert grade_text("This is an unsafe unsupported claim.") == "F"
    assert grade_text("This is a model inference from partial context.") == "D"
