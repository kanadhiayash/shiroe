"""Mission schema + validator."""

from __future__ import annotations

from dataclasses import dataclass, field


MISSION_SCHEMA = "shiroe.mission/v1"


class MissionSchemaError(ValueError):
    pass


@dataclass
class Mission:
    id: str
    version: int
    triggers: list[str] = field(default_factory=list)
    required_seats: list[dict] = field(default_factory=list)
    execution_graph: list[str] = field(default_factory=list)
    required_outputs: list[str] = field(default_factory=list)
    completion: dict = field(default_factory=dict)


def validate(data: dict) -> Mission:
    if data.get("schema") != MISSION_SCHEMA:
        raise MissionSchemaError(
            f"expected schema {MISSION_SCHEMA!r}, got {data.get('schema')!r}"
        )
    for k in ("id", "version", "required_seats", "execution_graph",
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
    graph = data["execution_graph"]
    if not isinstance(graph, list) or not graph:
        raise MissionSchemaError("execution_graph must be non-empty")
    for step in graph:
        if step not in seat_ids:
            raise MissionSchemaError(
                f"execution_graph step {step!r} not in required_seats"
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
        execution_graph=list(graph),
        required_outputs=list(data["required_outputs"]),
        completion=dict(data["completion"]),
    )
