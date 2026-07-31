"""PrivacyGuard tests."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from shiroe.core.errors import GuardRejection
from shiroe.guards.privacy_guard import classify_text, redact_file, scan_path
from shiroe.guards.write_gate import write_from_proposal
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
    scaffold_project(root, name="privacy", privacy="abstract", tier="auto", parent="")
    return MemoryStore.from_root(root)


def test_privacy_classification_and_redaction(tmp_path: Path) -> None:
    redact_md = tmp_path / "REDACT.md"
    text = "token ghp_AbCdEfGhIjKlMnOpQrStUvWxYz0123"
    result = classify_text(text, redact_md_path=redact_md)
    assert result["privacy_class"] == "secret"
    assert "[REDACTED:credentials]" in result["redacted_text"]


def test_privacy_scan_and_redact_file(tmp_path: Path) -> None:
    doc = tmp_path / "doc.md"
    doc.write_text("Internal path /Users/example/project and email user@example.com", encoding="utf-8")
    findings = scan_path(tmp_path, redact_md_path=tmp_path / "REDACT.md")
    assert findings
    cleaned, finding = redact_file(doc, redact_md_path=tmp_path / "REDACT.md")
    assert finding is not None
    assert "/Users/example/project" not in cleaned


def test_privacy_cli_scan_and_classify(repo_root: Path, tmp_path: Path) -> None:
    _store(tmp_path)
    doc = tmp_path / "docs" / "secret.md"
    doc.parent.mkdir()
    doc.write_text("access token abcdefghijklmnopqrstuvwxyz", encoding="utf-8")

    scan = _run(repo_root, tmp_path, ["privacy", "scan", "docs/"])
    assert scan.returncode == 0
    assert "credentials" in scan.stdout
    strict = _run(repo_root, tmp_path, ["privacy", "scan", "docs/", "--strict"])
    assert strict.returncode == 1

    classified = _run(repo_root, tmp_path, ["privacy", "classify", "safe public copy"])
    assert classified.returncode == 0
    assert json.loads(classified.stdout)["privacy_class"] == "public"


def test_write_gate_blocks_secret_claim(tmp_path: Path) -> None:
    store = _store(tmp_path)
    proposal = tmp_path / "proposal.json"
    proposal.write_text(
        json.dumps(
            {
                "type": "preference",
                "title": "Secret token",
                "claim": "Use ghp_AbCdEfGhIjKlMnOpQrStUvWxYz0123 for releases.",
                "privacy_class": "internal",
                "evidence_grade": "C",
                "source_refs": ["user-input"],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(GuardRejection) as exc:
        write_from_proposal(proposal, store)
    assert exc.value.guard == "PrivacyGuard"
