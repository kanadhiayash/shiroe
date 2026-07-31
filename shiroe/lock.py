"""
shiroe.lock — Advisory single-writer lock + atomic write helpers.

Two primitives:

1. MemoryLock — context manager. Creates memory/.lock atomically via O_EXCL.
   Writers wait with bounded retries + backoff (default ZEREF_LOCK_TIMEOUT_SECONDS,
   overridable per lock). On timeout, LockError carries holder PID + timestamp.
   Pass timeout_seconds=0 for the legacy fail-fast behaviour.

2. atomic_write(path, content) — write to <path>.tmp, fsync, rename.
   On crash mid-write, the original file is preserved intact.

Usage:
    from shiroe.lock import MemoryLock, atomic_write, LockError
    with MemoryLock(Path("memory")):
        atomic_write(Path("memory/DECISIONS.md"), new_content)
"""

from __future__ import annotations

import os
import random
import time
from pathlib import Path


DEFAULT_LOCK_TIMEOUT_SECONDS = 10.0
_BACKOFF_INITIAL_SECONDS = 0.01
_BACKOFF_MAX_SECONDS = 0.25


def default_lock_timeout() -> float:
    """Bounded lock wait in seconds; configurable via ZEREF_LOCK_TIMEOUT_SECONDS."""
    raw = os.environ.get("ZEREF_LOCK_TIMEOUT_SECONDS", "")
    try:
        value = float(raw)
    except ValueError:
        return DEFAULT_LOCK_TIMEOUT_SECONDS
    return max(0.0, value)


class LockError(RuntimeError):
    """Raised when memory/.lock is already held by another writer."""


class MemoryLock:
    """Advisory POSIX lock for the memory/ tree using O_CREAT|O_EXCL.

    Contending writers queue with retries + exponential backoff until
    `timeout_seconds` elapses, then fail explicitly with LockError.
    `timeout_seconds=0` keeps the legacy fail-fast semantics.
    """

    def __init__(self, memory_dir: Path, timeout_seconds: float | None = None):
        self.lockfile = memory_dir / ".lock"
        self.timeout = default_lock_timeout() if timeout_seconds is None else max(0.0, timeout_seconds)
        self._fd: int | None = None

    def acquire(self) -> None:
        deadline = time.monotonic() + self.timeout
        backoff = _BACKOFF_INITIAL_SECONDS
        first = True
        while True:
            try:
                self._fd = os.open(
                    str(self.lockfile),
                    os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                    0o600,
                )
                holder = f"pid={os.getpid()}\nacquired={time.time()}\n"
                os.write(self._fd, holder.encode())
                return
            except FileExistsError:
                if first and self.timeout == 0:
                    raise LockError(
                        f"memory/.lock held by {self._read_holder()}. Another writer is active."
                    )
                first = False
                if time.monotonic() >= deadline:
                    raise LockError(
                        f"timed out after {self.timeout}s waiting for memory/.lock "
                        f"(held by {self._read_holder()})"
                    )
                # Bounded exponential backoff with jitter so contending
                # writers queue instead of thundering on the lockfile.
                time.sleep(min(backoff, max(0.0, deadline - time.monotonic())))
                backoff = min(backoff * 2, _BACKOFF_MAX_SECONDS) * (0.5 + random.random())
                backoff = min(max(backoff, _BACKOFF_INITIAL_SECONDS), _BACKOFF_MAX_SECONDS)

    def release(self) -> None:
        if self._fd is not None:
            try:
                os.close(self._fd)
            except OSError:
                pass
            self._fd = None
        try:
            self.lockfile.unlink()
        except FileNotFoundError:
            pass

    def _read_holder(self) -> str:
        try:
            return self.lockfile.read_text(errors="ignore").strip().replace("\n", " ")
        except Exception:
            return "<unknown>"

    def __enter__(self) -> "MemoryLock":
        self.acquire()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.release()


def atomic_write(path: Path, content: str) -> None:
    """Write content to path atomically: tmp -> fsync -> replace."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.parent.mkdir(parents=True, exist_ok=True)

    fd = os.open(str(tmp), os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o644)
    try:
        os.write(fd, content.encode("utf-8"))
        os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(tmp, path)


def atomic_append(path: Path, content: str) -> None:
    """True O(1) append: single O_APPEND write + fsync.

    Appending record N must not rewrite the N-1 prior records. A single
    write(2) to an O_APPEND descriptor lands the payload contiguously at
    EOF, so prior records are never touched and a crash can only affect
    the final record.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(path), os.O_CREAT | os.O_WRONLY | os.O_APPEND, 0o644)
    try:
        os.write(fd, content.encode("utf-8"))
        os.fsync(fd)
    finally:
        os.close(fd)
