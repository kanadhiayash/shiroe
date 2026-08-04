"""
Concurrent writers and injected failures must leave state and history consistent.

The primitives looked right in isolation and were wrong together:

* `atomic_write` staged through a fixed `<name>.tmp`. Two writers to the same
  path shared one staging file, so each could overwrite the other's partially
  written bytes and then `os.replace` the result into place. The rename is
  atomic; what it renames was not.

* `_write_conflicts_md` read `CONFLICTS.md` *before* taking the lock and wrote
  it inside. Two detections could therefore read the same base text, each append
  its own block, and the second write would drop the first -- a lost update, and
  a silently lost contradiction, which is the one class of record this system
  exists to not lose.

These tests use threads rather than processes on purpose: `MemoryLock` is an
advisory `O_CREAT|O_EXCL` file lock, so it serialises threads and processes
alike, and a lost update reproduces either way.
"""

from __future__ import annotations

import os
import threading
from pathlib import Path

import pytest

from shiroe.lock import MemoryLock, atomic_write


WRITERS = 8


def _run_concurrently(fn, count: int = WRITERS) -> list[BaseException]:
    """Run `fn(i)` on `count` threads released together. Returns any exceptions."""
    start = threading.Barrier(count)
    errors: list[BaseException] = []
    lock = threading.Lock()

    def _worker(i: int) -> None:
        start.wait()
        try:
            fn(i)
        except BaseException as exc:  # noqa: BLE001 - collected, asserted by caller
            with lock:
                errors.append(exc)

    threads = [threading.Thread(target=_worker, args=(i,)) for i in range(count)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return errors


def test_concurrent_atomic_writes_never_leave_a_torn_file(tmp_path: Path) -> None:
    """Every reader must see one writer's complete content, never a blend.

    With a shared `<name>.tmp` staging path, two writers interleave inside the
    same file and `os.replace` publishes the mixture.
    """
    target = tmp_path / "state.md"
    payloads = {i: f"writer-{i}:" + ("x" * 200_000) + f":end-{i}\n" for i in range(WRITERS)}

    errors = _run_concurrently(lambda i: atomic_write(target, payloads[i]))
    assert not errors, f"atomic_write raised under contention: {errors!r}"

    final = target.read_text(encoding="utf-8")
    assert final in payloads.values(), (
        "published file is not any single writer's content -- staging was shared"
    )


def test_atomic_write_leaves_no_staging_files_behind(tmp_path: Path) -> None:
    """A unique staging name must still be cleaned up, or tmp files accumulate."""
    target = tmp_path / "state.md"
    _run_concurrently(lambda i: atomic_write(target, f"content-{i}\n"))

    leftovers = [p.name for p in tmp_path.iterdir() if p.name != target.name]
    assert not leftovers, f"staging files left behind: {leftovers}"


def test_concurrent_contradiction_writes_do_not_lose_any(tmp_path: Path) -> None:
    """The gate: every detected contradiction must survive concurrent surfacing.

    Reading outside the lock lets two writers share a base text; the later write
    then erases the earlier one's block.
    """
    from shiroe.memory import contradictions as contradictions_mod

    memory_dir = tmp_path / "memory"
    memory_dir.mkdir(parents=True, exist_ok=True)

    def _surface(i: int) -> None:
        contradictions_mod._write_conflicts_md(tmp_path, [{
            "id": f"contradiction_{i:02d}",
            "summary": f"claim {i} disagrees with its counterpart",
            "links": [
                {"relation": "left_claim", "target_id": f"atom_left_{i}"},
                {"relation": "right_claim", "target_id": f"atom_right_{i}"},
            ],
        }])

    errors = _run_concurrently(_surface)
    assert not errors, f"surfacing raised under contention: {errors!r}"

    text = (memory_dir / "CONFLICTS.md").read_text(encoding="utf-8")
    missing = [i for i in range(WRITERS) if f"## contradiction_{i:02d}" not in text]
    assert not missing, (
        f"contradictions lost to concurrent writes: {missing} -- "
        "CONFLICTS.md must be read and written under the same lock"
    )


def test_a_failed_write_does_not_destroy_the_previous_content(tmp_path: Path) -> None:
    """An injected failure mid-write must leave the prior file intact.

    This is what staging buys: the reader either sees the old file or the new
    one, never a truncated one, even when the writer dies partway.
    """
    target = tmp_path / "state.md"
    atomic_write(target, "original content\n")

    real_write = os.write
    calls = {"n": 0}

    def _exploding_write(fd: int, data: bytes) -> int:
        calls["n"] += 1
        if calls["n"] == 1:
            raise OSError("injected disk failure")
        return real_write(fd, data)

    os.write = _exploding_write
    try:
        with pytest.raises(OSError, match="injected disk failure"):
            atomic_write(target, "replacement content\n")
    finally:
        os.write = real_write

    assert target.read_text(encoding="utf-8") == "original content\n", (
        "a failed write destroyed the previous content"
    )
    leftovers = [p.name for p in tmp_path.iterdir() if p.name != target.name]
    assert not leftovers, f"failed write left staging files behind: {leftovers}"


def test_memory_lock_actually_serialises_writers(tmp_path: Path) -> None:
    """The lock is the premise of everything above; prove it excludes."""
    memory_dir = tmp_path / "memory"
    memory_dir.mkdir(parents=True, exist_ok=True)

    overlaps = {"n": 0}
    inside = {"n": 0}
    guard = threading.Lock()

    def _critical(_i: int) -> None:
        with MemoryLock(memory_dir, timeout_seconds=10.0):
            with guard:
                inside["n"] += 1
                if inside["n"] > 1:
                    overlaps["n"] += 1
            # Long enough that unserialised writers would reliably overlap.
            threading.Event().wait(0.01)
            with guard:
                inside["n"] -= 1

    errors = _run_concurrently(_critical)
    assert not errors, f"lock acquisition failed: {errors!r}"
    assert overlaps["n"] == 0, "two writers were inside the lock at once"
