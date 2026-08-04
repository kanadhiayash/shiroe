"""
privacy-audit: allow-file "Lineage importer references example repo paths + intake fields as schema; no user data."

Sandbox importer for Shiroe lineage repositories.

Foreign repositories are cloned only into .shiroe-sandbox and represented in
tracked code by metadata, hashes, counts, and exclusion records.
"""

from __future__ import annotations

import hashlib
import json
import os

from shiroe.env import getenv as env_get
import ssl
import subprocess
import urllib.error
import urllib.request
from collections import defaultdict
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Callable

from shiroe.lineage.intake import LineageRow, load_rows


SANDBOX_ROOT = Path(".shiroe-sandbox") / "lineage"
MANIFEST_NAME = "manifest.json"
TEXT_SUFFIXES = {
    "",
    ".adoc",
    ".cfg",
    ".csv",
    ".css",
    ".go",
    ".h",
    ".html",
    ".ini",
    ".java",
    ".js",
    ".json",
    ".jsx",
    ".md",
    ".py",
    ".rs",
    ".sh",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".yaml",
    ".yml",
}
EXCLUDED_PARTS = {
    ".git",
    ".hg",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "__pycache__",
    "build",
    "coverage",
    "dist",
    "node_modules",
    "site-packages",
    "target",
    "vendor",
}


@dataclass(frozen=True)
class SourceIdentity:
    """Resolved identity for a lineage source."""

    repo_url: str
    owner_name: str
    default_branch: str
    commit_sha: str
    archived: bool
    private: bool
    updated_at: str
    license: str
    subdirectory: str
    row_ids: list[int]
    source_kind: str
    notes: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "repo_url": self.repo_url,
            "owner_name": self.owner_name,
            "default_branch": self.default_branch,
            "commit_sha": self.commit_sha,
            "archived": self.archived,
            "private": self.private,
            "updated_at": self.updated_at,
            "license": self.license,
            "subdirectory": self.subdirectory,
            "row_ids": self.row_ids,
            "source_kind": self.source_kind,
            "notes": self.notes,
        }


INTAKE_CSV_NAME = "SHIROE_64_repo_lineage_intake.csv"
# SHR-013: pre-rename filename. The CSV is local-only and hand-maintained, so
# the old name is still accepted; dropping it is SHR-027 (PR 04).
LEGACY_INTAKE_CSV_NAME = "ZRF_64_repo_lineage_intake.csv"


def default_csv_path(root: Path | None = None) -> Path:
    """Return the conventional local intake path without committing it."""
    base = root or Path.cwd()
    env_path = env_get("LINEAGE_INTAKE_CSV")
    if env_path:
        return Path(env_path)
    for parent in (base, base.parent):
        for name in (INTAKE_CSV_NAME, LEGACY_INTAKE_CSV_NAME):
            if (parent / name).exists():
                return parent / name
    return base.parent / INTAKE_CSV_NAME


def import_lineage(
    csv_path: str | Path | None = None,
    *,
    root: str | Path | None = None,
    sandbox: bool = False,
    latest_default: bool = False,
    dry_run: bool = False,
    resolver: Callable[[LineageRow], SourceIdentity] | None = None,
    cloner: Callable[[SourceIdentity, Path], None] | None = None,
) -> dict[str, Any]:
    """Resolve, optionally clone, and inventory lineage sources."""
    project_root = Path(root or Path.cwd())
    source_csv = Path(csv_path) if csv_path else default_csv_path(project_root)
    rows = load_rows(source_csv)
    grouped = _group_rows(rows)
    resolver = resolver or resolve_identity
    cloner = cloner or clone_source

    identities: list[SourceIdentity] = []
    issues: list[dict[str, Any]] = []
    for group_rows in grouped.values():
        try:
            resolved = resolver(group_rows[0])
            identities.append(replace(resolved, row_ids=[row.id for row in group_rows]))
        except Exception as exc:  # noqa: BLE001 - report source-level failures deterministically.
            issues.append({
                "row_ids": [row.id for row in group_rows],
                "repo_url": group_rows[0].repo_url,
                "error": str(exc),
            })

    manifest: dict[str, Any] = {
        "passed": not issues,
        "dry_run": dry_run,
        "latest_default": latest_default,
        "sandbox": str(project_root / SANDBOX_ROOT),
        "csv": str(source_csv),
        "source_count": len(identities),
        "row_count": len(rows),
        "issues": issues,
        "sources": [],
    }

    for identity in identities:
        source_record: dict[str, Any] = {"identity": identity.to_dict()}
        if not dry_run and sandbox and identity.source_kind == "github":
            checkout = project_root / SANDBOX_ROOT / _source_slug(identity)
            cloner(identity, checkout)
            inventory_root = checkout / identity.subdirectory if identity.subdirectory else checkout
            source_record["inventory"] = inventory_tree(inventory_root)
        elif dry_run:
            source_record["planned_action"] = "resolve_only"
        elif identity.source_kind != "github":
            source_record["planned_action"] = "citation_only"
        else:
            source_record["planned_action"] = "sandbox_disabled"
        manifest["sources"].append(source_record)

    if sandbox and not dry_run:
        sandbox_root = project_root / SANDBOX_ROOT
        sandbox_root.mkdir(parents=True, exist_ok=True)
        (sandbox_root / MANIFEST_NAME).write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    return manifest


def resolve_identity(row: LineageRow) -> SourceIdentity:
    """Resolve source metadata from GitHub or concept citation metadata."""
    if row.source_kind != "github":
        return SourceIdentity(
            repo_url=row.repo_url,
            owner_name=row.repo_name,
            default_branch="",
            commit_sha="",
            archived=False,
            private=False,
            updated_at="",
            license="citation",
            subdirectory=row.subdirectory,
            row_ids=[row.id],
            source_kind="non_github",
            notes=["concept_source"],
        )

    data = _github_json(f"https://api.github.com/repos/{row.github_repo}")
    default_branch = str(data.get("default_branch") or "")
    branch = _github_json(f"https://api.github.com/repos/{row.github_repo}/branches/{default_branch}")
    license_data = data.get("license") or {}
    archived = bool(data.get("archived"))
    notes = ["archived_reference"] if archived else []
    return SourceIdentity(
        repo_url=f"https://github.com/{row.github_repo}",
        owner_name=row.github_repo,
        default_branch=default_branch,
        commit_sha=str(((branch.get("commit") or {}).get("sha")) or ""),
        archived=archived,
        private=bool(data.get("private")),
        updated_at=str(data.get("updated_at") or ""),
        license=str(license_data.get("spdx_id") or license_data.get("key") or "NOASSERTION"),
        subdirectory=row.subdirectory,
        row_ids=[row.id],
        source_kind="github",
        notes=notes,
    )


def clone_source(identity: SourceIdentity, checkout: Path) -> None:
    """Clone or refresh one GitHub source at its resolved default branch."""
    checkout.parent.mkdir(parents=True, exist_ok=True)
    if checkout.exists():
        subprocess.run(["git", "-C", str(checkout), "fetch", "--depth", "1", "origin", identity.default_branch],
                       check=True, stdout=subprocess.DEVNULL)
        subprocess.run(["git", "-C", str(checkout), "checkout", "--detach", identity.commit_sha],
                       check=True, stdout=subprocess.DEVNULL)
        return
    subprocess.run([
        "git",
        "clone",
        "--depth",
        "1",
        "--branch",
        identity.default_branch,
        identity.repo_url,
        str(checkout),
    ], check=True, stdout=subprocess.DEVNULL)
    subprocess.run(["git", "-C", str(checkout), "checkout", "--detach", identity.commit_sha],
                   check=True, stdout=subprocess.DEVNULL)


def inventory_tree(root: Path) -> dict[str, Any]:
    """Inventory text files under root while recording excluded paths."""
    files: list[dict[str, Any]] = []
    exclusions: list[dict[str, str]] = []
    if not root.exists():
        return {"root": str(root), "files": files, "exclusions": [{"path": str(root), "reason": "missing"}]}

    for path in sorted(root.rglob("*")):
        if path.is_dir():
            continue
        rel = path.relative_to(root)
        reason = _exclusion_reason(rel, path)
        if reason:
            exclusions.append({"path": rel.as_posix(), "reason": reason})
            continue
        try:
            data = path.read_bytes()
        except OSError as exc:
            exclusions.append({"path": rel.as_posix(), "reason": f"read_error:{exc.__class__.__name__}"})
            continue
        if b"\0" in data:
            exclusions.append({"path": rel.as_posix(), "reason": "binary"})
            continue
        text = data.decode("utf-8", errors="replace")
        lines = text.splitlines()
        files.append({
            "path": rel.as_posix(),
            "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
            "line_count": len(lines),
            "line_hash": hashlib.sha256("\n".join(
                hashlib.sha256(line.encode("utf-8", errors="replace")).hexdigest()
                for line in lines
            ).encode("utf-8")).hexdigest(),
        })
    return {
        "root": str(root),
        "file_count": len(files),
        "line_count": sum(item["line_count"] for item in files),
        "files": files,
        "exclusions": exclusions,
    }


def _github_json(url: str) -> dict[str, Any]:
    # R3 policy gate — refuse unless SHARING_POLICY.md github.enabled OR env override
    # (see SHR-AUDIT-002). Fall back to raising the standard policy exception so
    # the caller can degrade gracefully rather than silently exfiltrating.
    from shiroe.security import load_policy, require_connector
    from shiroe.memory.core import discover_project_root
    require_connector(load_policy(discover_project_root()), "github",
                      purpose=f"lineage:{url}")
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "shiroe-lineage-importer",
    }
    auth_value = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if auth_value:
        headers["Authorization"] = f"Bearer {auth_value}"
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API error {exc.code} for {url}: {body[:200]}") from exc
    except urllib.error.URLError as exc:
        if isinstance(exc.reason, ssl.SSLError):
            return _github_json_via_gh(url)
        raise


def _github_json_via_gh(url: str) -> dict[str, Any]:
    prefix = "https://api.github.com/"
    if not url.startswith(prefix):
        raise RuntimeError(f"cannot resolve non-GitHub API URL with gh: {url}")
    api_path = url.removeprefix(prefix)
    try:
        completed = subprocess.run(
            ["gh", "api", api_path],
            check=True,
            text=True,
            capture_output=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        raise RuntimeError(f"GitHub API SSL fallback failed for {api_path}: {exc}") from exc
    return json.loads(completed.stdout)


def _group_rows(rows: list[LineageRow]) -> dict[str, list[LineageRow]]:
    grouped: dict[str, list[LineageRow]] = defaultdict(list)
    for row in rows:
        key = row.github_repo.lower() if row.github_repo else f"concept:{row.repo_url}"
        if row.subdirectory:
            key = f"{key}//{row.subdirectory}"
        grouped[key].append(row)
    return dict(sorted(grouped.items()))


def _source_slug(identity: SourceIdentity) -> str:
    slug = identity.owner_name.lower().replace("/", "__").replace(" ", "-")
    if identity.subdirectory:
        slug += "__" + identity.subdirectory.replace("/", "__")
    return slug


def _exclusion_reason(rel: Path, path: Path) -> str:
    if any(part in EXCLUDED_PARTS for part in rel.parts):
        return "excluded_path"
    suffix = path.suffix.lower()
    if suffix not in TEXT_SUFFIXES:
        return "non_text_extension"
    try:
        if path.stat().st_size > 1_000_000:
            return "large_file"
    except OSError:
        return "stat_error"
    return ""
