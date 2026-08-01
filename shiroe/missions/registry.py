"""In-memory registry populated by :func:`shiroe.missions.loader.load_all`."""

from __future__ import annotations

from pathlib import Path

from shiroe.missions.loader import load_all
from shiroe.missions.schema import Mission


MISSION_IDS = ("solo", "build", "research", "red", "audit", "ship")


def list_missions(root: Path | str) -> list[Mission]:
    return load_all(root)


def get_mission(root: Path | str, mission_id: str) -> Mission:
    for mission in load_all(root):
        if mission.id == mission_id:
            return mission
    raise KeyError(f"mission {mission_id!r} not found under {Path(root)/'missions'}")
