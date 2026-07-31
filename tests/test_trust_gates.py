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


def _run(repo_root: Path, cwd: Path, args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "shiroe", *args],
        capture_output=True,
        text=True,
        cwd=str(cwd),
        env=_env(repo_root),
    )


def _init(repo_root: Path, root: Path) -> None:
    result = _run(
        repo_root,
        repo_root,
        ["init", "--directory", str(root), "--name", "trust-test", "--privacy", "abstract", "--tier", "auto", "--parent", ""],
    )
    assert result.returncode == 0, result.stderr


def _add(repo_root: Path, root: Path, claim: str, evidence: str = "A") -> str:
    result = _run(
        repo_root,
        root,
        ["memory", "add", "--type", "fact", "--claim", claim, "--source", "manual:test", "--evidence", evidence, "--json"],
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)["id"]


def test_evidence_grade_and_fact_audit(repo_root: Path, tmp_path: Path) -> None:
    _init(repo_root, tmp_path)
    _add(repo_root, tmp_path, "Zeref maybe beats every benchmark.", evidence="unverified")

    graded = _run(repo_root, tmp_path, ["evidence", "grade", "Claim from file", "--source", "README.md", "--source-type", "file"])
    assert graded.returncode == 0
    assert json.loads(graded.stdout)["evidence"] == "A"

    audited = _run(repo_root, tmp_path, ["facts", "audit"])
    assert audited.returncode == 1
    assert json.loads(audited.stdout)["findings"]


def test_contradiction_scan_propose_and_resolve(repo_root: Path, tmp_path: Path) -> None:
    _init(repo_root, tmp_path)
    left = _add(repo_root, tmp_path, "Connector sync is enabled.")
    right = _add(repo_root, tmp_path, "Connector sync is disabled.")

    scanned = _run(repo_root, tmp_path, ["contradictions", "scan"])
    assert scanned.returncode == 0, scanned.stderr
    created = json.loads(scanned.stdout)["created"]
    contradiction_id = created[0]["id"]

    proposed = _run(repo_root, tmp_path, ["contradictions", "propose", contradiction_id])
    assert proposed.returncode == 0
    assert "User arbitration required" in json.loads(proposed.stdout)["proposal"]

    resolved = _run(
        repo_root,
        tmp_path,
        ["contradictions", "resolve", contradiction_id, "--winner", left, "--reason", "manual test"],
    )
    assert resolved.returncode == 0, resolved.stderr
    payload = json.loads(resolved.stdout)
    assert payload["winner"] == left
    assert payload["superseded"][0]["id"] == right
