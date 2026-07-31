"""Guarded memory write pipeline tests."""

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
        cwd=str(cwd),
        capture_output=True,
        text=True,
        env=_env(repo_root),
    )


def _init(repo_root: Path, root: Path) -> None:
    result = _run(
        repo_root,
        repo_root,
        [
            "init",
            "--directory",
            str(root),
            "--name",
            "write-gate",
            "--privacy",
            "abstract",
            "--tier",
            "auto",
            "--parent",
            "",
        ],
    )
    assert result.returncode == 0, result.stderr


def _events(root: Path) -> list[dict]:
    lines = (root / "memory" / "state" / "events.jsonl").read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def test_memory_propose_and_guarded_write(repo_root: Path, tmp_path: Path) -> None:
    _init(repo_root, tmp_path)

    proposed = _run(
        repo_root,
        tmp_path,
        ["memory", "propose", "User prefers public-safe copy by default.", "--json"],
    )
    assert proposed.returncode == 0, proposed.stderr
    proposal = json.loads(proposed.stdout)
    assert proposal["privacy_class"] == "internal"
    assert proposal["evidence_grade"] == "C"
    assert proposal["source_refs"] == ["user-input"]
    assert (tmp_path / "proposal.json").is_file()

    written = _run(repo_root, tmp_path, ["memory", "write", "--from", "proposal.json", "--json"])
    assert written.returncode == 0, written.stderr
    card = json.loads(written.stdout)
    # Guarded writes now land in the canonical atom store, whose ids are
    # `<type>_<digest>` rather than the old card `mem_` prefix.
    assert card["id"].startswith("preference_")
    assert card["type"] == "preference"

    listed = _run(repo_root, tmp_path, ["memory", "list", "--type", "preference", "--json"])
    assert listed.returncode == 0, listed.stderr
    assert json.loads(listed.stdout)[0]["id"] == card["id"]

    shown = _run(repo_root, tmp_path, ["memory", "show", card["id"]])
    assert shown.returncode == 0, shown.stderr
    assert json.loads(shown.stdout)["claim"] == "User prefers public-safe copy by default."

    assert any(event["event"] == "memory-write-accepted" for event in _events(tmp_path))


def test_memory_write_rejects_missing_evidence_grade(repo_root: Path, tmp_path: Path) -> None:
    _init(repo_root, tmp_path)
    proposal = {
        "type": "fact",
        "title": "missing evidence",
        "claim": "Shiroe has guarded writes.",
        "privacy_class": "internal",
        "source_refs": ["README.md"],
    }
    (tmp_path / "proposal.json").write_text(json.dumps(proposal), encoding="utf-8")

    result = _run(repo_root, tmp_path, ["memory", "write", "--from", "proposal.json"])
    assert result.returncode == 1
    assert "Write blocked by WriteGate" in result.stdout
    assert "evidence_grade" in result.stdout
    assert any(event["event"] == "memory-write-rejected" for event in _events(tmp_path))


def test_memory_write_rejects_missing_privacy_class(repo_root: Path, tmp_path: Path) -> None:
    _init(repo_root, tmp_path)
    proposal = {
        "type": "fact",
        "title": "missing privacy",
        "claim": "Shiroe has guarded writes.",
        "evidence_grade": "B",
        "source_refs": ["README.md"],
    }
    (tmp_path / "proposal.json").write_text(json.dumps(proposal), encoding="utf-8")

    result = _run(repo_root, tmp_path, ["memory", "write", "--from", "proposal.json"])
    assert result.returncode == 1
    assert "privacy_class" in result.stdout


def test_memory_write_rejects_missing_source_refs(repo_root: Path, tmp_path: Path) -> None:
    _init(repo_root, tmp_path)
    proposal = {
        "type": "fact",
        "title": "missing source",
        "claim": "Shiroe has guarded writes.",
        "privacy_class": "internal",
        "evidence_grade": "B",
    }
    (tmp_path / "proposal.json").write_text(json.dumps(proposal), encoding="utf-8")

    result = _run(repo_root, tmp_path, ["memory", "write", "--from", "proposal.json"])
    assert result.returncode == 1
    assert "Write blocked by EvidenceGuard" in result.stdout


def test_memory_write_rejects_secret_and_contradiction(repo_root: Path, tmp_path: Path) -> None:
    _init(repo_root, tmp_path)
    secret = {
        "type": "fact",
        "title": "secret",
        "claim": "Store this secret.",
        "privacy_class": "secret",
        "evidence_grade": "B",
        "source_refs": ["user-input"],
    }
    (tmp_path / "secret.json").write_text(json.dumps(secret), encoding="utf-8")
    secret_result = _run(repo_root, tmp_path, ["memory", "write", "--from", "secret.json"])
    assert secret_result.returncode == 1
    assert "Write blocked by PrivacyGuard" in secret_result.stdout

    first = {
        "type": "decision",
        "title": "routing policy",
        "claim": "Use flagship models only for critical tasks.",
        "privacy_class": "internal",
        "evidence_grade": "B",
        "source_refs": ["AGENTS.md"],
    }
    second = {**first, "claim": "Use flagship models for every task."}
    (tmp_path / "first.json").write_text(json.dumps(first), encoding="utf-8")
    (tmp_path / "second.json").write_text(json.dumps(second), encoding="utf-8")
    assert _run(repo_root, tmp_path, ["memory", "write", "--from", "first.json"]).returncode == 0
    conflict = _run(repo_root, tmp_path, ["memory", "write", "--from", "second.json"])
    assert conflict.returncode == 1
    assert "Write blocked by ContradictionGuard" in conflict.stdout


def test_memory_archive_and_supersede_cli(repo_root: Path, tmp_path: Path) -> None:
    _init(repo_root, tmp_path)
    first = {
        "type": "decision",
        "title": "old policy",
        "claim": "Use old policy.",
        "privacy_class": "internal",
        "evidence_grade": "B",
        "source_refs": ["README.md"],
    }
    second = {**first, "title": "new policy", "claim": "Use new policy."}
    (tmp_path / "first.json").write_text(json.dumps(first), encoding="utf-8")
    (tmp_path / "second.json").write_text(json.dumps(second), encoding="utf-8")
    first_card = json.loads(_run(repo_root, tmp_path, ["memory", "write", "--from", "first.json", "--json"]).stdout)
    second_card = json.loads(_run(repo_root, tmp_path, ["memory", "write", "--from", "second.json", "--json"]).stdout)

    archived = _run(repo_root, tmp_path, ["memory", "archive", first_card["id"], "--json"])
    assert archived.returncode == 0, archived.stderr
    assert json.loads(archived.stdout)["status"] == "archived"

    superseded = _run(
        repo_root,
        tmp_path,
        ["memory", "supersede", first_card["id"], "--with", second_card["id"], "--json"],
    )
    assert superseded.returncode == 0, superseded.stderr
    result = json.loads(superseded.stdout)
    assert result["superseded"]["superseded_by"] == second_card["id"]
    assert first_card["id"] in result["replacement"]["supersedes"]


def test_write_gate_rejects_every_factguard_blocked_phrase(tmp_path: Path) -> None:
    """The write gate must reject exactly what FactGuard rejects.

    The gate used to restate a four-phrase subset of BLOCKED_PATTERNS inline.
    Phrases added to FactGuard afterwards ("production-ready", "all gates
    pass", "fully verified", ...) were refused by `shiroe fact check` but still
    accepted into memory. This pins the two to one shared table.
    """
    from shiroe.core.errors import GuardRejection
    from shiroe.guards.fact_guard import BLOCKED_PATTERNS
    from shiroe.guards.write_gate import _validate_gate
    from shiroe.memory.core import scaffold_project
    from shiroe.memory_state import MemoryStore

    (tmp_path / "AGENTS.md").write_text("# AGENTS.md\n", encoding="utf-8")
    scaffold_project(tmp_path, name="factguard-parity", privacy="abstract",
                     tier="auto", parent="")
    store = MemoryStore.from_root(tmp_path)

    phrases = [p for group in BLOCKED_PATTERNS.values() for p in group]
    assert len(phrases) >= 12, "BLOCKED_PATTERNS unexpectedly small"

    for phrase in phrases:
        proposal = {
            "type": "fact",
            "title": f"claim {phrase}",
            "claim": f"Shiroe {phrase} today.",
            "privacy_class": "internal",
            "evidence_grade": "B",
            "source_refs": ["README.md"],
        }
        try:
            _validate_gate(proposal, store)
        except GuardRejection as exc:
            assert exc.guard == "FactGuard", (
                f"{phrase!r} rejected by {exc.guard}, expected FactGuard"
            )
            continue
        raise AssertionError(f"write gate accepted FactGuard-blocked phrase: {phrase!r}")


def test_memory_write_cli_rejects_previously_missed_phrase(repo_root: Path, tmp_path: Path) -> None:
    """End-to-end: a phrase outside the old inline subset is now blocked."""
    _init(repo_root, tmp_path)
    proposal = {
        "type": "fact",
        "title": "readiness",
        "claim": "Shiroe is production-ready for all workloads.",
        "privacy_class": "internal",
        "evidence_grade": "B",
        "source_refs": ["README.md"],
    }
    (tmp_path / "proposal.json").write_text(json.dumps(proposal), encoding="utf-8")

    result = _run(repo_root, tmp_path, ["memory", "write", "--from", "proposal.json"])
    assert result.returncode == 1
    assert "FactGuard" in result.stdout
    assert any(event["event"] == "memory-write-rejected" for event in _events(tmp_path))
