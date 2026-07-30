"""
privacy-audit: allow-file "Checkpoint store names run-directory field names as spec; benchmark task text only, no user data."

Append-only checkpoint store for resumable scored runs.

A full external campaign on local hardware runs for days. It will be
interrupted — a laptop sleeps, a daemon restarts, a quota window closes, a
process is killed. Without a checkpoint the entire run is lost and every
completed generation has to be paid for again in wall-clock time.

Design constraints, in the order that matters:

* **Never lose completed work.** One JSON line per finished (task_id, arm),
  flushed and fsynced before the next call starts. A kill at any instant
  loses at most the in-flight case.
* **Never double-charge.** Resume skips any (task_id, arm) already recorded,
  so a restart re-reads results instead of regenerating them. On a metered
  judge that is real money; on a local generator it is real hours.
* **Never silently resume across a changed configuration.** The run's
  identity — benchmark, arms, seed, limit, models, prompt hash, chunk size —
  is written once as a header and re-checked on resume. Resuming a run whose
  prompt or model changed would silently mix two run series into one set of
  numbers, which is the exact defect that makes a published result
  indefensible.
* **Tolerate a truncated tail.** A process killed mid-write leaves a partial
  final line. That line is discarded on read rather than aborting the resume.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Iterator

RECORDS_FILENAME = "records.jsonl"
HEADER_FILENAME = "run-header.json"


class CheckpointMismatchError(RuntimeError):
    """Resume was attempted against a run with different parameters.

    Refusing is the point: silently continuing would merge results generated
    under two different configurations into one reported number.
    """


def _key(task_id: str, arm: str) -> str:
    return f"{arm}\x00{task_id}"


class CheckpointStore:
    """Append-only (task_id, arm) result log for one run directory."""

    def __init__(self, run_dir: str | Path) -> None:
        self.run_dir = Path(run_dir)
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.records_path = self.run_dir / RECORDS_FILENAME
        self.header_path = self.run_dir / HEADER_FILENAME
        self._handle = None

    # --- identity -----------------------------------------------------------

    def bind(self, header: dict[str, Any]) -> None:
        """Write the run identity, or verify it matches on resume."""
        if self.header_path.exists():
            existing = json.loads(self.header_path.read_text(encoding="utf-8"))
            differing = {
                field: (existing.get(field), header.get(field))
                for field in set(existing) | set(header)
                if existing.get(field) != header.get(field)
            }
            if differing:
                detail = ", ".join(
                    f"{field}: {before!r} -> {after!r}"
                    for field, (before, after) in sorted(differing.items())
                )
                raise CheckpointMismatchError(
                    f"refusing to resume {self.run_dir}: run parameters changed ({detail}). "
                    "Results generated under different parameters are a different run "
                    "series and must not be merged. Start a new run directory."
                )
            return
        self.header_path.write_text(
            json.dumps(header, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

    # --- reading ------------------------------------------------------------

    def completed(self) -> dict[str, dict[str, Any]]:
        """Every recorded result, keyed by (arm, task_id).

        A truncated final line — the signature of a process killed mid-write —
        is dropped rather than raising, so an interrupted run can always be
        resumed.
        """
        if not self.records_path.exists():
            return {}
        results: dict[str, dict[str, Any]] = {}
        for line in self.records_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue  # partial tail from an interrupted write
            task_id, arm = record.get("task_id"), record.get("arm")
            if task_id is None or arm is None:
                continue
            results[_key(task_id, arm)] = record
        return results

    def has(self, task_id: str, arm: str, completed: dict[str, dict[str, Any]]) -> bool:
        return _key(task_id, arm) in completed

    @staticmethod
    def get(task_id: str, arm: str, completed: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
        return completed.get(_key(task_id, arm))

    # --- writing ------------------------------------------------------------

    def append(self, record: dict[str, Any]) -> None:
        """Durably record one finished case.

        flush + fsync on every record. That costs a syscall per case and is
        worth it: the alternative is discovering after a crash that the last
        several hours of generation were buffered and never written.
        """
        if self._handle is None:
            self._handle = self.records_path.open("a", encoding="utf-8")
        self._handle.write(json.dumps(record, sort_keys=True) + "\n")
        self._handle.flush()
        os.fsync(self._handle.fileno())

    def close(self) -> None:
        if self._handle is not None:
            self._handle.close()
            self._handle = None

    def __enter__(self) -> "CheckpointStore":
        return self

    def __exit__(self, *exc) -> bool:
        self.close()
        return False

    def __iter__(self) -> Iterator[dict[str, Any]]:
        return iter(self.completed().values())
