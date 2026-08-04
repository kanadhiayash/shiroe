"""Mission schema + validator."""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field


MISSION_SCHEMA = "shiroe.mission/v1"

# SHR-009: the ordered step list is a sequence, not a graph. Mission files
# written against the pre-rename name still load, warning exactly once.
SEQUENCE_FIELD = "execution_sequence"
LEGACY_SEQUENCE_FIELD = "execution_graph"


class MissionSchemaError(ValueError):
    pass


@dataclass
class Mission:
    id: str
    version: int
    triggers: list[str] = field(default_factory=list)
    required_seats: list[dict] = field(default_factory=list)
    execution_sequence: list[str] = field(default_factory=list)
    required_outputs: list[str] = field(default_factory=list)
    completion: dict = field(default_factory=dict)


def _read_sequence(data: dict) -> list:
    """Return the ordered step list, accepting the pre-SHR-009 field once."""
    has_new = SEQUENCE_FIELD in data
    has_legacy = LEGACY_SEQUENCE_FIELD in data
    if has_new and has_legacy:
        raise MissionSchemaError(
            f"declare {SEQUENCE_FIELD!r} or {LEGACY_SEQUENCE_FIELD!r}, not both"
        )
    if has_new:
        return data[SEQUENCE_FIELD]
    if has_legacy:
        warnings.warn(
            f"mission field {LEGACY_SEQUENCE_FIELD!r} is deprecated; "
            f"rename it to {SEQUENCE_FIELD!r} (SHR-009)",
            DeprecationWarning,
            stacklevel=3,
        )
        return data[LEGACY_SEQUENCE_FIELD]
    raise MissionSchemaError(f"missing field {SEQUENCE_FIELD!r}")


def validate(data: dict) -> Mission:
    if data.get("schema") != MISSION_SCHEMA:
        raise MissionSchemaError(
            f"expected schema {MISSION_SCHEMA!r}, got {data.get('schema')!r}"
        )
    sequence = _read_sequence(data)
    for k in ("id", "version", "required_seats",
              "required_outputs", "completion"):
        if k not in data:
            raise MissionSchemaError(f"missing field {k!r}")
    seats = data["required_seats"]
    if not isinstance(seats, list) or not seats:
        raise MissionSchemaError("required_seats must be a non-empty list")
    seat_ids: set[str] = set()
    for seat in seats:
        if not isinstance(seat, dict):
            raise MissionSchemaError("each seat must be a mapping")
        if "id" not in seat:
            raise MissionSchemaError("seat missing id")
        if seat["id"] in seat_ids:
            raise MissionSchemaError(f"duplicate seat id {seat['id']!r}")
        seat_ids.add(seat["id"])
        provides = seat.get("provides") or []
        if not isinstance(provides, list) or not provides:
            raise MissionSchemaError(
                f"seat {seat['id']!r} must declare non-empty provides[]"
            )
    if not isinstance(sequence, list) or not sequence:
        raise MissionSchemaError(f"{SEQUENCE_FIELD} must be non-empty")
    for step in sequence:
        if step not in seat_ids:
            raise MissionSchemaError(
                f"{SEQUENCE_FIELD} step {step!r} not in required_seats"
            )
    # Independence: referenced ids must exist.
    for seat in seats:
        indep = (seat.get("constraints") or {}).get("independent_from") or []
        for other in indep:
            if other not in seat_ids:
                raise MissionSchemaError(
                    f"seat {seat['id']!r} independent_from references "
                    f"unknown seat {other!r}"
                )
            if other == seat["id"]:
                raise MissionSchemaError(
                    f"seat {seat['id']!r} cannot be independent from itself"
                )
    return Mission(
        id=str(data["id"]),
        version=int(data["version"]),
        triggers=list(data.get("triggers") or []),
        required_seats=list(seats),
        execution_sequence=list(sequence),
        required_outputs=list(data["required_outputs"]),
        completion=dict(data["completion"]),
    )
