"""ZRF-67 — plugin identity + install freshness.

Covers two things:
  1. The display-name rebrand landed on live surfaces, without touching the
     `zeref-os` compatibility identifier (package name / plugin name /
     registry namespace), and without rewriting historical records.
  2. The installed-state manifest (`zeref doctor --installation`,
     `zeref version --verbose`) is well-formed, its digests are real, it can
     detect that a previously recorded manifest is stale against current
     content, and computing it never touches — let alone loses — memory/.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from zeref.release.manifest import _packaged_files, build_manifest, is_stale

# Specific current *display* surfaces — the doc/manifest text a user actually
# reads. Deliberately NOT a blanket repo grep: historical records (CHANGELOG,
# scripts/zeref-publish-releases.sh), migration notes (skills/memory-import-export,
# skills/parent-sync), and test fixtures are allowed to keep the old name.
DISPLAY_SURFACES = [
    "README.md", "SKILL.md", "AGENTS.md", "CLAUDE.md", "CODEX.md", "GEMINI.md",
    "LLAMA.md", "GITHUB_OS.md", "config/PROJECT.md", "commands/status.md",
    "commands/start.md", "zeref/__init__.py", "zeref/cli.py",
]


def _env(repo_root: Path) -> dict:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo_root) + os.pathsep + env.get("PYTHONPATH", "")
    return env


def _run(repo_root: Path, cwd: Path, args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "zeref", *args],
        cwd=str(cwd), capture_output=True, text=True, env=_env(repo_root),
    )


# ---------------------------------------------------------------------------
# Part A — identity
# ---------------------------------------------------------------------------

def test_no_display_surface_renders_old_name(repo_root: Path) -> None:
    for rel in DISPLAY_SURFACES:
        text = (repo_root / rel).read_text(encoding="utf-8")
        assert "Zeref OS" not in text, f"{rel} still renders the old display name"

    plugin = json.loads((repo_root / ".claude-plugin/plugin.json").read_text(encoding="utf-8"))
    assert "Zeref OS" not in plugin["description"]

    marketplace = json.loads((repo_root / ".claude-plugin/marketplace.json").read_text(encoding="utf-8"))
    assert "Zeref OS" not in marketplace["description"]
    for entry in marketplace["plugins"]:
        assert "Zeref OS" not in entry.get("description", "")

    pyproject_text = (repo_root / "pyproject.toml").read_text(encoding="utf-8")
    desc_line = next(line for line in pyproject_text.splitlines() if line.startswith("description"))
    assert "Zeref OS" not in desc_line


def test_compat_identifier_intact(repo_root: Path) -> None:
    """The zeref-os package/plugin identifier is a separate migration decision
    (out of scope for ZRF-67) and must survive the display-name rebrand."""
    pyproject_text = (repo_root / "pyproject.toml").read_text(encoding="utf-8")
    assert 'name = "zeref-os"' in pyproject_text

    plugin = json.loads((repo_root / ".claude-plugin/plugin.json").read_text(encoding="utf-8"))
    assert plugin["name"] == "zeref-os"

    marketplace = json.loads((repo_root / ".claude-plugin/marketplace.json").read_text(encoding="utf-8"))
    assert marketplace["name"] == "zeref-os"
    assert marketplace["plugins"][0]["name"] == "zeref-os"

    registry = json.loads((repo_root / "zeref-registry.json").read_text(encoding="utf-8"))
    assert "zeref-os" in registry["$schema"]


# ---------------------------------------------------------------------------
# Part B — installed-state manifest
# ---------------------------------------------------------------------------

def test_manifest_well_formed_and_digests_match_actual_files(repo_root: Path) -> None:
    manifest = build_manifest(repo_root)

    assert manifest.schema_version == 1
    assert manifest.product_name == "Zeref Memory Engine"
    assert manifest.compat_id == "zeref-os"
    assert manifest.package_file_count > 0
    assert manifest.package_digest.startswith("sha256:")

    expected_registry = "sha256:" + hashlib.sha256(
        (repo_root / "zeref-registry.json").read_bytes()
    ).hexdigest()
    assert manifest.registry_digest == expected_registry

    expected_agents = "sha256:" + hashlib.sha256(
        (repo_root / "AGENTS.md").read_bytes()
    ).hexdigest()
    assert manifest.agents_digest == expected_agents


def test_doctor_installation_and_version_verbose_cli(repo_root: Path) -> None:
    doctor = _run(repo_root, repo_root, ["doctor", "--installation"])
    assert doctor.returncode == 0, doctor.stdout + doctor.stderr
    assert "version:" in doctor.stdout
    assert "git_sha:" in doctor.stdout

    version = _run(repo_root, repo_root, ["version", "--verbose"])
    assert version.returncode == 0, version.stdout + version.stderr
    assert "version:" in version.stdout
    assert "git_sha:" in version.stdout

    # The existing global --version flag must keep working unchanged.
    flag = _run(repo_root, repo_root, ["--version"])
    assert flag.returncode == 0
    assert flag.stdout.strip().startswith("zeref ")

    bare = _run(repo_root, repo_root, ["version"])
    assert bare.returncode == 0
    assert bare.stdout.strip().startswith("zeref ")


def test_is_stale_detects_upgrade(repo_root: Path) -> None:
    fresh = build_manifest(repo_root).to_dict()
    assert is_stale(fresh, repo_root) is False

    old = dict(fresh, git_sha="0" * 40, version="0.0.1")
    assert is_stale(old, repo_root) is True


def test_memory_survives_manifest_rebuild(tmp_path: Path) -> None:
    """Computing/rebuilding the manifest must never read or depend on memory/
    content, so a real reinstall (which regenerates packaged files) can never
    touch it."""
    root = tmp_path
    (root / "memory").mkdir()
    marker = root / "memory" / "hot.md"
    marker.write_text("user-private-note", encoding="utf-8")
    (root / "pyproject.toml").write_text(
        '[project]\nname = "zeref-os"\n', encoding="utf-8"
    )
    (root / "AGENTS.md").write_text("# AGENTS.md\n", encoding="utf-8")
    (root / "zeref-registry.json").write_text("{}", encoding="utf-8")

    before_digest = build_manifest(root).package_digest
    packaged_rel_paths = {str(p.relative_to(root)) for p in _packaged_files(root)}
    assert not any(p.startswith("memory/") for p in packaged_rel_paths)

    # Simulate a reinstall: every packaged (non-memory) file gets rewritten.
    (root / "AGENTS.md").write_text("# AGENTS.md (updated)\n", encoding="utf-8")
    after_digest = build_manifest(root).package_digest

    assert marker.read_text(encoding="utf-8") == "user-private-note"
    assert before_digest != after_digest
