"""Load execution policies from ``policies/*.yaml``."""

from __future__ import annotations

from pathlib import Path

from shiroe.execution_policies.schema import ExecutionPolicy, validate
from shiroe.yaml_subset import parse_file


def load(path: Path | str) -> ExecutionPolicy:
    return validate(parse_file(path))


def load_all(root: Path | str) -> list[ExecutionPolicy]:
    root = Path(root)
    pdir = root / "policies"
    if not pdir.exists():
        return []
    return [load(p) for p in sorted(pdir.glob("*.yaml"))]


def get_policy(root: Path | str, policy_id: str) -> ExecutionPolicy:
    for policy in load_all(root):
        if policy.id == policy_id:
            return policy
    raise KeyError(f"policy {policy_id!r} not found under {Path(root)/'policies'}")
