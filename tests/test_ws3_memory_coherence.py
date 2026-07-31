"""WS3 regression tests — memory coherence, structured contradictions,
append scaling, and concurrent writers (audit zeref-sandbox-audit-2026-07-13).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from shiroe.lock import LockError, MemoryLock
from shiroe.memory.atom_store import AtomStore
from shiroe.memory.contradictions import detect_conflict, scan_contradictions, suggest_winner
from shiroe.memory.recall import recall
from shiroe.memory.schemas import create_atom


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
            "--name", "ws3-coherence",
            "--privacy", "abstract",
            "--tier", "auto",
            "--parent", "",
        ],
    )
    assert result.returncode == 0, result.stderr


def _fact(claim: str, *, evidence: str = "unverified", provenance: str = "") -> dict:
    return create_atom(
        atom_type="fact",
        claim=claim,
        summary=claim,
        source="manual:ws3-test",
        evidence=evidence,
        provenance=provenance or claim,
    )


# ---------------------------------------------------------------------------
# Audit case 1: add -> search must round-trip on one canonical store
# ---------------------------------------------------------------------------

def test_memory_add_then_search_round_trip(repo_root: Path, tmp_path: Path) -> None:
    _init(repo_root, tmp_path)

    added = _run(
        repo_root,
        tmp_path,
        [
            "memory", "add",
            "--type", "fact",
            "--claim", "Kubernetes migration owner is the platform team",
            "--source", "manual:ws3",
            "--json",
        ],
    )
    assert added.returncode == 0, added.stderr
    atom = json.loads(added.stdout)

    searched = _run(repo_root, tmp_path, ["memory", "search", "Kubernetes migration", "--json"])
    assert searched.returncode == 0, searched.stderr
    results = json.loads(searched.stdout)
    assert results, "add -> search must return the added fact (audit: split store returned [])"
    ids = {row.get("id") for row in results}
    assert atom["id"] in ids
    match = next(row for row in results if row.get("id") == atom["id"])
    assert match["claim"] == "Kubernetes migration owner is the platform team"


def test_memory_search_stays_coherent_with_stale_index(repo_root: Path, tmp_path: Path) -> None:
    _init(repo_root, tmp_path)
    store = AtomStore(tmp_path)
    store.append(_fact("Indexed fact about databases"))

    indexed = _run(repo_root, tmp_path, ["memory", "index", "--json"])
    assert indexed.returncode == 0, indexed.stderr

    # Appended after the index build: must still be searchable.
    store.append(_fact("Fresh fact about databases added after indexing"))
    searched = _run(repo_root, tmp_path, ["memory", "search", "databases", "--json"])
    assert searched.returncode == 0, searched.stderr
    claims = {row.get("claim") for row in json.loads(searched.stdout)}
    assert "Fresh fact about databases added after indexing" in claims


# ---------------------------------------------------------------------------
# Audit case 2: two launch dates (grades B and C) must surface
# ---------------------------------------------------------------------------

def test_two_launch_dates_surface_in_open_contradictions(repo_root: Path, tmp_path: Path) -> None:
    _init(repo_root, tmp_path)
    store = AtomStore(tmp_path)
    atom_b = store.append(_fact("Launch date is 2026-09-01", evidence="B"))
    atom_c = store.append(_fact("Launch date is 2026-10-15", evidence="C"))

    # Surfaced at recall time even before any scan persisted the conflict.
    live = recall(tmp_path, "launch date")
    assert live["open_contradictions"], "audit regression: open_contradictions was empty"
    detected = live["open_contradictions"][0]
    assert detected["suggested_winner"] == atom_b["id"]
    assert "human arbitration required" in detected["summary"]

    # Scan persists the contradiction atom and surfaces it in CONFLICTS.md.
    result = scan_contradictions(tmp_path)
    assert result["count"] == 1
    created = result["created"][0]
    linked = {link["target_id"] for link in created["links"]}
    assert linked == {atom_b["id"], atom_c["id"]}
    assert f"suggested_winner={atom_b['id']}" in created["summary"]
    # Not auto-resolved: both source atoms stay active, conflict stays open.
    assert store.get(atom_b["id"])["status"] == "active"
    assert store.get(atom_c["id"])["status"] == "active"
    assert created["status"] == "active"

    conflicts_md = (tmp_path / "memory" / "CONFLICTS.md").read_text(encoding="utf-8")
    assert created["id"] in conflicts_md
    assert atom_b["id"] in conflicts_md and atom_c["id"] in conflicts_md
    assert "**Status:** open" in conflicts_md

    # After the scan, recall reports the persisted atom exactly once.
    persisted = recall(tmp_path, "launch date")
    assert [c["id"] for c in persisted["open_contradictions"]] == [created["id"]]


def test_structured_conflict_detection_kinds(tmp_path: Path) -> None:
    def fact(claim, evidence="unverified", entities=None):
        return {**_fact(claim, evidence=evidence), "entities": entities or []}

    # Dates in different formats normalize and collide.
    assert detect_conflict(
        fact("Launch date is September 1, 2026"), fact("Launch date is 2026-10-15")
    )
    # Quantities with units.
    assert detect_conflict(
        fact("API latency budget is 200 ms"), fact("API latency budget is 350ms")
    )
    # Status keywords (legacy antonym pairs still covered).
    assert detect_conflict(
        fact("Connector sync is enabled."), fact("Connector sync is disabled.")
    )
    # Identity/bare-number fields.
    assert detect_conflict(fact("Primary DB port is 5432"), fact("Primary DB port is 5433"))
    # Same value: no conflict.
    assert detect_conflict(
        fact("Launch date is 2026-09-01"), fact("Launch date is September 1, 2026")
    ) is None
    # Different templates: no conflict.
    assert detect_conflict(
        fact("Launch date is 2026-09-01"), fact("Freeze date is 2026-10-15")
    ) is None
    # Disjoint named entities: no conflict.
    assert detect_conflict(
        fact("Port is 5432", entities=["db-a"]), fact("Port is 5433", entities=["db-b"])
    ) is None
    # Evidence precedence suggestion, tie -> None.
    left = fact("Launch date is 2026-09-01", evidence="B")
    right = fact("Launch date is 2026-10-15", evidence="C")
    assert suggest_winner(left, right) == left["id"]
    assert suggest_winner(fact("x", evidence="B"), fact("y", evidence="B")) is None


# ---------------------------------------------------------------------------
# Concurrency: writers queue with bounded wait; explicit failure on timeout
# ---------------------------------------------------------------------------

def test_concurrent_writers_all_succeed_no_lost_writes(tmp_path: Path) -> None:
    (tmp_path / "memory").mkdir()
    workers = 20
    errors: list[Exception] = []

    def writer(i: int) -> None:
        try:
            AtomStore(tmp_path).append(_fact(f"concurrent fact {i}", provenance=f"writer-{i}"))
        except Exception as exc:  # noqa: BLE001 - recorded for assertion
            errors.append(exc)

    threads = [threading.Thread(target=writer, args=(i,)) for i in range(workers)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert not errors, f"writers must queue, not fail instantly: {errors}"
    atoms = AtomStore(tmp_path).load(atom_type="fact")
    assert len(atoms) == workers, "no lost writes"
    assert len({atom["id"] for atom in atoms}) == workers


def test_lock_timeout_fails_explicitly(tmp_path: Path) -> None:
    memory_dir = tmp_path / "memory"
    memory_dir.mkdir()
    with MemoryLock(memory_dir):
        contender = MemoryLock(memory_dir, timeout_seconds=0.2)
        start = time.monotonic()
        with pytest.raises(LockError, match="timed out"):
            contender.acquire()
        assert time.monotonic() - start >= 0.2
    # Legacy fail-fast semantics preserved for timeout_seconds=0.
    with MemoryLock(memory_dir):
        with pytest.raises(LockError, match="Another writer is active"):
            MemoryLock(memory_dir, timeout_seconds=0).acquire()


def test_duplicate_atom_id_still_rejected(tmp_path: Path) -> None:
    (tmp_path / "memory").mkdir()
    store = AtomStore(tmp_path)
    atom = _fact("dedup check fact")
    store.append(atom)
    with pytest.raises(Exception, match="duplicate atom id"):
        store.append(atom)
    # A second store instance (fresh process analogue) also detects the dup.
    with pytest.raises(Exception, match="duplicate atom id"):
        AtomStore(tmp_path).append(atom)


# ---------------------------------------------------------------------------
# Scale: appending atom N must not rewrite the N-1 prior atoms
# ---------------------------------------------------------------------------

@pytest.mark.slow
def test_append_scales_near_linearly(tmp_path: Path) -> None:
    def bench(n: int) -> float:
        root = tmp_path / f"scale_{n}"
        (root / "memory").mkdir(parents=True)
        store = AtomStore(root)
        start = time.perf_counter()
        for i in range(n):
            store.append(_fact(f"scale fact {i}", provenance=f"scale-{n}-{i}"))
        return time.perf_counter() - start

    bench(50)  # warm-up (imports, fs caches)
    t_small = bench(100)
    t_large = bench(1000)
    ratio = t_large / max(t_small, 1e-6)
    # Linear growth is ~10x; the audited quadratic behaviour was ~29x
    # (0.24s -> 7.07s). Generous CI margin, still far below quadratic.
    assert ratio < 20, f"append no longer linear: 100={t_small:.3f}s 1000={t_large:.3f}s ratio={ratio:.1f}"
