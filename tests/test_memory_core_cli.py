"""Structured Memory Core CLI tests."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from shiroe.compat.legacy_identity import LEGACY_V1_STATE_DB_NAME


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


def _init(repo_root: Path, tmp_path: Path) -> None:
    result = _run(
        repo_root,
        repo_root,
        [
            "init",
            "--directory",
            str(tmp_path),
            "--name",
            "memory-core",
            "--privacy",
            "abstract",
            "--tier",
            "auto",
            "--parent",
            "",
        ],
    )
    assert result.returncode == 0, result.stderr


def test_memory_cli_add_search_get_update_history_explain(repo_root: Path, tmp_path: Path) -> None:
    _init(repo_root, tmp_path)

    added = _run(
        repo_root,
        tmp_path,
        [
            "memory",
            "add",
            "--kind",
            "decision",
            "--title",
            "memory state decision",
            "--body",
            "SQLite state should support explainable recall for Shiroe.",
            "--entity",
            "Shiroe",
            "--tag",
            "retrieval",
            "--layer",
            "L2",
            "--source-ref",
            "docs/memory-core.md",
            "--confidence",
            "high",
            "--authority",
            "canonical",
            "--json",
        ],
    )
    assert added.returncode == 0, added.stderr
    item = json.loads(added.stdout)
    assert item["id"] == 1
    assert item["source_ref"] == "docs/memory-core.md"
    assert item["layer"] == "L2"
    assert item["confidence"] == "high"
    assert item["authority"] == "canonical"

    state_dir = tmp_path / "memory" / "state"
    assert (state_dir / LEGACY_V1_STATE_DB_NAME).is_file()
    assert (state_dir / "schema.json").is_file()
    assert "memory-state.v1" in (state_dir / "schema.json").read_text(encoding="utf-8")

    events = (state_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()
    assert events
    assert json.loads(events[-1])["event"] == "memory-add"

    searched = _run(
        repo_root,
        tmp_path,
        ["memory", "search", "recall", "--entity", "Shiroe", "--layer", "L2", "--json"],
    )
    assert searched.returncode == 0, searched.stderr
    results = json.loads(searched.stdout)
    assert len(results) == 1
    assert results[0]["id"] == 1
    assert "why_returned" in results[0]
    assert "source_ref=docs/memory-core.md" in results[0]["why_returned"]

    fetched = _run(repo_root, tmp_path, ["memory", "get", "1", "--json"])
    assert fetched.returncode == 0, fetched.stderr
    assert json.loads(fetched.stdout)["title"] == "memory state decision"

    updated = _run(
        repo_root,
        tmp_path,
        [
            "memory",
            "update",
            "1",
            "--body",
            "SQLite state supports keyword and entity recall.",
            "--layer",
            "L1",
            "--confidence",
            "medium",
            "--json",
        ],
    )
    assert updated.returncode == 0, updated.stderr
    updated_item = json.loads(updated.stdout)
    assert updated_item["confidence"] == "medium"
    assert updated_item["layer"] == "L1"

    history = _run(repo_root, tmp_path, ["memory", "history", "1", "--json"])
    assert history.returncode == 0, history.stderr
    history_events = json.loads(history.stdout)
    assert [event["event"] for event in history_events] == ["memory-update", "memory-add"]

    explained = _run(repo_root, tmp_path, ["memory", "explain", "1", "--query", "entity", "--json"])
    assert explained.returncode == 0, explained.stderr
    explanation = json.loads(explained.stdout)
    assert explanation["why_returned"]
    assert "confidence=medium" in explanation["why_returned"]
    assert "layer=L1" in explanation["why_returned"]

    views = _run(repo_root, tmp_path, ["memory", "views", "--json"])
    assert views.returncode == 0, views.stderr
    written = json.loads(views.stdout)
    assert sorted(written) == [
        "assumptions.md",
        "decisions.md",
        "operating-profile.md",
        "project-profile.md",
        "risks.md",
        "unknowns.md",
    ]

    decisions = (tmp_path / "memory" / "views" / "decisions.md").read_text(encoding="utf-8")
    assert f"Generated from `memory/state/{LEGACY_V1_STATE_DB_NAME}`" in decisions
    assert "memory state decision" in decisions
    assert "**Layer:** L1" in decisions
    assert "**Source:** docs/memory-core.md" in decisions

    risks = (tmp_path / "memory" / "views" / "risks.md").read_text(encoding="utf-8")
    assert "_(no `risk` entries)_" in risks
