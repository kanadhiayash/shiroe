"""Load missions from ``missions/*.yaml``."""

from __future__ import annotations

from pathlib import Path

from shiroe.missions.schema import Mission, validate
from shiroe.yaml_subset import parse_file


def load(path: Path | str) -> Mission:
    return validate(parse_file(path))


def load_all(root: Path | str) -> list[Mission]:
    root = Path(root)
    mdir = root / "missions"
    if not mdir.exists():
        return []
    return [load(p) for p in sorted(mdir.glob("*.yaml"))]
