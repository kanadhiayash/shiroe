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
        [
            "init",
            "--directory", str(root),
            "--name", "loop-test",
            "--privacy", "abstract",
            "--tier", "auto",
            "--parent", "",
        ],
    )
    assert result.returncode == 0, result.stderr


def _add_decision(repo_root: Path, root: Path) -> dict:
    result = _run(
        repo_root,
        root,
        [
            "memory", "add",
            "--type", "decision",
            "--claim", "Use deterministic prompts before optional model rewrite.",
            "--source", "tests/test_prompt_handoff_loop.py",
            "--source-type", "file",
            "--evidence", "A",
            "--confidence", "high",
            "--privacy", "public-safe",
            "--json",
        ],
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_prompt_classify_rewrite_and_inject(repo_root: Path, tmp_path: Path) -> None:
    prompt = "I want to change the dashboard screen buttons just like we did on settings page."

    classified = _run(repo_root, tmp_path, ["prompt", "classify", prompt, "--json"])
    assert classified.returncode == 0, classified.stderr
    assert json.loads(classified.stdout)["classification"] == "SEMI_STRUCTURED"

    rewritten = _run(repo_root, tmp_path, ["prompt", "rewrite", prompt, "--json"])
    assert rewritten.returncode == 0, rewritten.stderr
    payload = json.loads(rewritten.stdout)
    assert payload["brief"]["objective"].startswith("I want to change")
    assert "settings page" in payload["brief"]["source_prompt"]

    injected = _run(repo_root, tmp_path, ["prompt", "inject", prompt, "--target", "codex", "--json"])
    assert injected.returncode == 0, injected.stderr
    assert "Codex Task Brief" in json.loads(injected.stdout)["content"]


def test_handoff_writes_markdown_and_json(repo_root: Path, tmp_path: Path) -> None:
    _init(repo_root, tmp_path)
    atom = _add_decision(repo_root, tmp_path)

    handoff = _run(repo_root, tmp_path, ["handoff", "codex", "--objective", "Continue PR 7.", "--json"])
    assert handoff.returncode == 0, handoff.stderr
    payload = json.loads(handoff.stdout)
    markdown_path = Path(payload["markdown"])
    json_path = Path(payload["json"])
    assert markdown_path.is_file()
    assert json_path.is_file()
    assert atom["id"] in markdown_path.read_text(encoding="utf-8")
    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert data["target"] == "codex"
    assert data["active_decisions"][0]["id"] == atom["id"]


def test_loop_plan_run_status_and_report_are_memory_safe(repo_root: Path, tmp_path: Path) -> None:
    _init(repo_root, tmp_path)

    planned = _run(
        repo_root,
        tmp_path,
        ["loop", "plan", "Update dashboard buttons", "--team", "small", "--max-iterations", "2", "--json"],
    )
    assert planned.returncode == 0, planned.stderr
    contract = json.loads(planned.stdout)
    assert contract["memory_permissions"]["direct_memory_write"] is False
    assert (tmp_path / "memory" / "loops" / contract["loop_id"] / "contract.json").is_file()

    before_atoms = sorted((tmp_path / "memory" / "l1_atoms").glob("*.jsonl"))
    before_text = {path.name: path.read_text(encoding="utf-8") for path in before_atoms}
    ran = _run(
        repo_root,
        tmp_path,
        ["loop", "run", "Update dashboard buttons", "--team", "small", "--max-iterations", "2", "--json"],
    )
    assert ran.returncode == 0, ran.stderr
    result = json.loads(ran.stdout)
    assert result["verification"]["passed"] is True
    proposal = json.loads(Path(result["memory_update_proposal"]).read_text(encoding="utf-8"))
    assert proposal["direct_memory_write"] is False
    after_text = {path.name: path.read_text(encoding="utf-8") for path in before_atoms}
    assert after_text == before_text

    status = _run(repo_root, tmp_path, ["loop", "status", "--json"])
    assert status.returncode == 0, status.stderr
    assert json.loads(status.stdout)["verification"]["passed"] is True

    report = _run(repo_root, tmp_path, ["loop", "report"])
    assert report.returncode == 0, report.stderr
    assert "Memory Update Proposal" in report.stdout
