"""ContradictionGuard tests."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from zeref.core.errors import GuardRejection
from zeref.guards.contradiction_guard import detect_incoming_conflicts, scan_store
from zeref.guards.write_gate import write_from_proposal
from zeref.memory import scaffold_project
from zeref.memory_state import MemoryStore


def _env(repo_root: Path) -> dict:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo_root) + os.pathsep + env.get("PYTHONPATH", "")
    return env


def _run(repo_root: Path, cwd: Path, args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "zeref", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        env=_env(repo_root),
    )


def _store(root: Path) -> MemoryStore:
    (root / "AGENTS.md").write_text("# AGENTS.md\n", encoding="utf-8")
    scaffold_project(root, name="contradictions", privacy="abstract", tier="auto", parent="")
    return MemoryStore.from_root(root)


def test_scan_store_detects_same_title_conflict(tmp_path: Path) -> None:
    store = _store(tmp_path)
    first = store.add_card(
        type="decision",
        title="Delivery source of truth",
        claim="Linear is the delivery source of truth.",
        privacy_class="internal",
        evidence_grade="B",
        source_refs=["docs/plans/ZEREF_HARDENING_RECON.md"],
    )
    second = store.add_card(
        type="decision",
        title="Delivery source of truth",
        claim="GitHub Issues are the delivery source of truth.",
        privacy_class="internal",
        evidence_grade="B",
        source_refs=["docs/plans/ZEREF_HARDENING_RECON.md"],
    )

    conflicts = scan_store(store)
    assert conflicts
    assert conflicts[0].existing_id in {first.id, second.id}
    assert conflicts[0].severity == "high"


def test_write_gate_blocks_and_records_conflict(tmp_path: Path) -> None:
    store = _store(tmp_path)
    # Seed through the guarded path so the existing claim lands in the
    # canonical atom store — the same store the gate reads when checking an
    # incoming write.
    seed = tmp_path / "seed.json"
    seed.write_text(
        json.dumps(
            {
                "type": "preference",
                "title": "Public copy default",
                "claim": "Use public-safe copy by default.",
                "privacy_class": "internal",
                "evidence_grade": "C",
                "source_refs": ["user-input"],
            }
        ),
        encoding="utf-8",
    )
    write_from_proposal(seed, store)
    proposal = tmp_path / "proposal.json"
    proposal.write_text(
        json.dumps(
            {
                "type": "preference",
                "title": "Public copy default",
                "claim": "Use internal exact copy by default.",
                "privacy_class": "internal",
                "evidence_grade": "C",
                "source_refs": ["user-input"],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(GuardRejection) as exc:
        write_from_proposal(proposal, store)
    assert exc.value.guard == "ContradictionGuard"
    assert "Public copy default" in (tmp_path / "memory" / "CONFLICTS.md").read_text(encoding="utf-8")


def test_contradictions_cli_scan_and_resolve(repo_root: Path, tmp_path: Path) -> None:
    store = _store(tmp_path)
    keep = store.add_card(
        type="decision",
        title="Automation policy",
        claim="Use Linear as delivery source of truth.",
        privacy_class="internal",
        evidence_grade="B",
        source_refs=["docs/plans/ZEREF_HARDENING_RECON.md"],
    )
    store.add_card(
        type="decision",
        title="Automation policy",
        claim="Use GitHub as delivery source of truth.",
        privacy_class="internal",
        evidence_grade="B",
        source_refs=["docs/plans/ZEREF_HARDENING_RECON.md"],
    )

    scan = _run(repo_root, tmp_path, ["contradictions", "scan", "memory/"])
    assert scan.returncode == 1
    conflict_id = scan.stdout.split()[1]

    shown = _run(repo_root, tmp_path, ["contradictions", "show", conflict_id])
    assert shown.returncode == 0
    assert json.loads(shown.stdout)["id"] == conflict_id

    resolved = _run(
        repo_root,
        tmp_path,
        ["contradictions", "resolve", conflict_id, "--winner", keep.id, "--reason", "User confirmed Linear."],
    )
    assert resolved.returncode == 0


def test_incoming_conflict_detection(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.add_card(
        type="preference",
        title="Tone",
        claim="Use direct plain language.",
        privacy_class="internal",
        evidence_grade="C",
        source_refs=["user-input"],
    )
    conflicts = detect_incoming_conflicts(store, title="Tone", claim="Use playful ornate language.")
    assert conflicts[0].incoming_id == "incoming"
