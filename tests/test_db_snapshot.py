"""
db-status reports backend availability.

This is a contract test: it asserts shape of the report, not which optional
backends happen to be installed in the test environment.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_db_status_reports_every_backend(repo_root: Path) -> None:
    r = subprocess.run(
        [sys.executable, "-m", "shiroe", "db-status"],
        capture_output=True, text=True, cwd=str(repo_root),
    )
    assert r.returncode == 0, r.stderr
    out = r.stdout
    for backend in ("sqlite3", "duckdb", "yaml", "litellm"):
        assert backend in out, f"db-status output missing {backend!r}: {out}"
    assert "Parquet export" in out
    assert "Rich YAML" in out
    assert "LLM grading" in out


def test_db_status_marks_sqlite_available(repo_root: Path) -> None:
    """sqlite3 ships with Python; it must always be marked available."""
    r = subprocess.run(
        [sys.executable, "-m", "shiroe", "db-status"],
        capture_output=True, text=True, cwd=str(repo_root),
    )
    assert "✔ sqlite3" in r.stdout, r.stdout
