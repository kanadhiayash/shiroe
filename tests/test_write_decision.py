"""
`zeref write-decision` round-trip: append → read back → grade.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def _env(repo_root: Path) -> dict:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo_root) + os.pathsep + env.get("PYTHONPATH", "")
    return env


def _init(repo_root: Path, root: Path) -> None:
    subprocess.run(
        [sys.executable, "-m", "shiroe", "init",
         "--directory", str(root),
         "--name", "decision-test",
         "--privacy", "abstract",
         "--tier", "auto",
         "--parent", ""],
        check=True, capture_output=True, text=True,
        cwd=str(repo_root), env=_env(repo_root),
    )


def test_write_decision_appends_to_DECISIONS(repo_root: Path, tmp_path: Path) -> None:
    _init(repo_root, tmp_path)
    r = subprocess.run(
        [sys.executable, "-m", "shiroe", "write-decision",
         "--title", "Adopt v1.0.0 trust-repair plan",
         "--why", "Eliminate version drift; harden privacy scrubber",
         "--evidence", "audit report 2026-06-19",
         "--grade", "high"],
        capture_output=True, text=True, cwd=str(tmp_path), env=_env(repo_root),
    )
    assert r.returncode == 0, (
        f"write-decision crashed:\nstdout:\n{r.stdout}\nstderr:\n{r.stderr}"
    )

    decisions = (tmp_path / "memory" / "DECISIONS.md").read_text(encoding="utf-8")
    assert "Adopt v1.0.0 trust-repair plan" in decisions
    assert "**Evidence grade:** high" in decisions
    assert "**Provenance:**" in decisions

    events = (tmp_path / "memory" / "patterns" / "PATTERNS.jsonl").read_text(encoding="utf-8")
    event = json.loads(events.strip())
    assert event["event"] == "wiki-write"
    assert event["target"] == "memory/DECISIONS.md"
    assert event["payload"]["summary"] == "Decision: Adopt v1.0.0 trust-repair plan"
    assert event["hash"].startswith("sha256:")
    assert event["evidence_grade"] == "high"


def test_write_decision_scrubs_pii(repo_root: Path, tmp_path: Path) -> None:
    _init(repo_root, tmp_path)
    r = subprocess.run(
        [sys.executable, "-m", "shiroe", "write-decision",
         "--title", "Rotate ghp_AbCdEfGhIjKlMnOpQrStUvWxYz0123",
         "--why", "Leaked in public log",
         "--evidence", "n/a",
         "--grade", "high"],
        capture_output=True, text=True, cwd=str(tmp_path), env=_env(repo_root),
    )
    assert r.returncode == 0, r.stderr

    decisions = (tmp_path / "memory" / "DECISIONS.md").read_text(encoding="utf-8")
    assert "ghp_AbCdEfGhIjKlMnOpQrStUvWxYz0123" not in decisions, (
        "credential leaked into DECISIONS.md"
    )
    assert "[REDACTED:credentials]" in decisions or "[PII:" in decisions
