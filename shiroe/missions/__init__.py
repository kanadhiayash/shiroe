"""Mission blueprints (vNext PR 6, ADR references team-packs → missions).

Missions define *what functional seats and outputs are needed* for a class
of task. They deliberately do NOT name specific capabilities or providers.
The team compiler (PR 7) picks concrete capabilities that fit each seat.
"""

from shiroe.missions.schema import (
    Mission,
    MissionSchemaError,
    MISSION_SCHEMA,
    validate,
)
from shiroe.missions.loader import load, load_all
from shiroe.missions.registry import (
    MISSION_IDS,
    get_mission,
    list_missions,
)

__all__ = [
    "Mission", "MissionSchemaError", "MISSION_SCHEMA", "validate",
    "load", "load_all",
    "MISSION_IDS", "get_mission", "list_missions",
]
