"""Load a policy stack from disk (JSON + existing PERMISSIONS.md).

Layer files (all optional):

- Runtime invariants  → hardcoded here.
- Project deny        → .shiroe/policy/deny.json
- Project defaults    → .shiroe/policy/defaults.json  OR  config/PERMISSIONS.md
- Global deny         → ~/.shiroe/policies/deny.json
- Global defaults     → ~/.shiroe/policies/defaults.json

Missing layers are dropped silently (default-deny still applies).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Iterable

from shiroe.policy.schema import ActionKind, PolicyLayer


def _runtime_invariants() -> PolicyLayer:
    # Denies that no config can turn off.
    return PolicyLayer(
        name="runtime-invariant",
        denies=frozenset({
            # Reserved: event-log tampering + redaction bypass are guarded in
            # code paths, not via ActionKind — the invariant layer's job here
            # is to remain a fail-closed anchor even when empty.
        }),
    )


def _load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _mk_layer(name: str, data: dict) -> PolicyLayer | None:
    if not data:
        return None
    denies = frozenset(ActionKind(k) for k in data.get("deny", []) if _is_kind(k))
    allows = frozenset(ActionKind(k) for k in data.get("allow", []) if _is_kind(k))
    if not denies and not allows and not data.get("fs_write_scopes"):
        return None
    return PolicyLayer(
        name=name,
        denies=denies,
        allows=allows,
        fs_write_scopes=tuple(data.get("fs_write_scopes", ())),
        fs_read_scopes=tuple(data.get("fs_read_scopes", ())),
        network_hosts=tuple(data.get("network_hosts", ())),
    )


def _is_kind(name: str) -> bool:
    try:
        ActionKind(name)
        return True
    except ValueError:
        return False


def _parse_permissions_md(path: Path) -> dict:
    """Very small parser for config/PERMISSIONS.md defaults."""
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8", errors="ignore")
    allow: list[str] = []
    deny: list[str] = []
    fs_write: list[str] = []
    fs_read: list[str] = []
    # Common lines: `network: denied`, `write: memory/`, `shell allow: [...]`
    for line in text.splitlines():
        low = line.strip().lower()
        if low.startswith("network:") and "denied" in low:
            deny.append(ActionKind.network.value)
        elif low.startswith("write:"):
            scope = line.split(":", 1)[1].strip()
            if scope:
                fs_write.append(scope)
                allow.append(ActionKind.fs_write.value)
        elif low.startswith("read:") or low.startswith("filesystem read:"):
            scope = line.split(":", 1)[1].strip()
            if scope:
                fs_read.append(scope)
                allow.append(ActionKind.fs_read.value)
    return {
        "allow": sorted(set(allow)),
        "deny": sorted(set(deny)),
        "fs_write_scopes": tuple(fs_write),
        "fs_read_scopes": tuple(fs_read),
    }


WORKSPACE_DIR = ".shiroe"
# Pre-rebrand workspace directory. Policy files here are deny rules and write
# scopes -- if a rename made them stop loading, nothing would error, the
# guard would just quietly stop denying. So the old location is still read
# when the new one has no file at that path.
_LEGACY_WORKSPACE_DIR = ".zeref"


def _workspace_file(root: Path, *parts: str) -> Path:
    """Path under .shiroe/, falling back to .zeref/ when only the old one exists."""
    current = root.joinpath(WORKSPACE_DIR, *parts)
    if current.exists():
        return current
    legacy = root.joinpath(_LEGACY_WORKSPACE_DIR, *parts)
    return legacy if legacy.exists() else current


def load_policy_stack(project_root: Path | str,
                      *,
                      global_root: Path | None = None) -> list[PolicyLayer]:
    project_root = Path(project_root)
    home = Path(os.path.expanduser("~"))
    if global_root is None:
        global_root = home / WORKSPACE_DIR / "policies"
        legacy_global = home / _LEGACY_WORKSPACE_DIR / "policies"
        if not global_root.exists() and legacy_global.exists():
            global_root = legacy_global

    stack: list[PolicyLayer] = [_runtime_invariants()]

    for src, name in (
        (_workspace_file(project_root, "policy", "deny.json"), "project-deny"),
        (global_root / "deny.json", "global-deny"),
    ):
        layer = _mk_layer(name, _load_json(src))
        if layer:
            stack.append(layer)

    perm_md = _parse_permissions_md(project_root / "config" / "PERMISSIONS.md")
    proj_defaults_json = _load_json(_workspace_file(project_root, "policy", "defaults.json"))
    merged_defaults = {
        "allow": sorted(set(perm_md.get("allow", []) + proj_defaults_json.get("allow", []))),
        "deny": sorted(set(perm_md.get("deny", []) + proj_defaults_json.get("deny", []))),
        "fs_write_scopes": tuple(perm_md.get("fs_write_scopes", ())) + tuple(proj_defaults_json.get("fs_write_scopes", ())),
        "fs_read_scopes":  tuple(perm_md.get("fs_read_scopes", ()))  + tuple(proj_defaults_json.get("fs_read_scopes", ())),
    }
    proj_defaults = _mk_layer("project-defaults", merged_defaults)
    if proj_defaults:
        stack.append(proj_defaults)

    global_defaults = _mk_layer("global-defaults", _load_json(global_root / "defaults.json"))
    if global_defaults:
        stack.append(global_defaults)

    return stack
