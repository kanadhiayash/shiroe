"""
Shared pytest fixtures for the Shiroe test suite.

Every test that touches disk uses a tmp_path-rooted "fake repo" so the real
checkout is never modified. The fake repo carries only the files the unit
under test needs.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent

# macOS/cloud-sync copy artifacts ("test_foo 2.py") are gitignored, but they
# still land on disk and pytest would collect them as real test modules —
# stale duplicates that fail against current code. Never collect them.
collect_ignore_glob = ["* [0-9].py"]


@pytest.fixture(scope="session")
def repo_root() -> Path:
    """Absolute path to the real checkout — read-only in tests."""
    return REPO_ROOT


@pytest.fixture()
def fake_repo(tmp_path: Path) -> Path:
    """
    Empty fake repo with the minimum scaffolding the CLI walks up to find.
    Tests build the rest of the layout they need.
    """
    (tmp_path / "AGENTS.md").write_text("# AGENTS.md\n", encoding="utf-8")
    (tmp_path / "memory").mkdir()
    (tmp_path / "config").mkdir()
    return tmp_path


@pytest.fixture()
def chdir(monkeypatch: pytest.MonkeyPatch):
    """Helper to cd into a path for the duration of a test."""
    def _cd(path: Path) -> None:
        monkeypatch.chdir(path)
    return _cd


@pytest.fixture(autouse=True)
def _ensure_repo_on_path() -> None:
    """Tests import `shiroe` from the repo, not from any installed copy."""
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
