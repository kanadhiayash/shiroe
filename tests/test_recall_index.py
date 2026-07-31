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


def _init_with_atom(repo_root: Path, root: Path) -> str:
    assert _run(
        repo_root,
        repo_root,
        [
            "init", "--directory", str(root), "--name", "recall-test",
            "--privacy", "abstract", "--tier", "auto", "--parent", "",
        ],
    ).returncode == 0
    added = _run(
        repo_root,
        root,
        [
            "memory", "add",
            "--type", "decision",
            "--claim", "Use SQLite FTS before optional vector search.",
            "--summary", "SQLite FTS is the first local recall backend.",
            "--source", "manual:test",
            "--evidence", "A",
            "--confidence", "high",
            "--json",
        ],
    )
    assert added.returncode == 0, added.stderr
    return json.loads(added.stdout)["id"]


def test_memory_index_and_recall_use_sqlite(repo_root: Path, tmp_path: Path) -> None:
    atom_id = _init_with_atom(repo_root, tmp_path)

    indexed = _run(repo_root, tmp_path, ["memory", "index", "--json"])
    assert indexed.returncode == 0, indexed.stderr
    assert json.loads(indexed.stdout)["atoms_indexed"] == 1

    recalled = _run(repo_root, tmp_path, ["recall", "SQLite FTS", "--json"])
    assert recalled.returncode == 0, recalled.stderr
    payload = json.loads(recalled.stdout)
    assert payload["source"] == "sqlite"
    assert payload["matched_atoms"][0]["atom"]["id"] == atom_id
    assert payload["evidence_grade"] == "A"


def test_recall_falls_back_to_jsonl_without_index(repo_root: Path, tmp_path: Path) -> None:
    atom_id = _init_with_atom(repo_root, tmp_path)

    recalled = _run(repo_root, tmp_path, ["recall", "vector search", "--json"])
    assert recalled.returncode == 0, recalled.stderr
    payload = json.loads(recalled.stdout)
    assert payload["source"] == "jsonl"
    assert payload["matched_atoms"][0]["atom"]["id"] == atom_id


def test_explain_search_returns_machine_readable_candidates(repo_root: Path, tmp_path: Path) -> None:
    atom_id = _init_with_atom(repo_root, tmp_path)
    assert _run(repo_root, tmp_path, ["memory", "index"]).returncode == 0

    explained = _run(repo_root, tmp_path, ["explain-search", "SQLite", "--json"])
    assert explained.returncode == 0, explained.stderr
    payload = json.loads(explained.stdout)
    assert payload["candidates"][0]["id"] == atom_id
    assert "why_selected" in payload["candidates"][0]
