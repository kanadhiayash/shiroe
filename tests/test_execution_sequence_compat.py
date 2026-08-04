"""SHR-009 — `execution_graph` is renamed to `execution_sequence`.

A mission's ordered step list is a sequence, not a graph (SHR-007). New mission
files declare `execution_sequence`; mission files written against the old name
must still load, and must say so exactly once.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest

from shiroe.missions.loader import load, load_all
from shiroe.missions.schema import MISSION_SCHEMA, MissionSchemaError, validate

REPO_ROOT = Path(__file__).resolve().parents[1]


def _mission_body(step_key: str) -> str:
    return (
        f"schema: {MISSION_SCHEMA}\n"
        "id: compat\n"
        "version: 1\n"
        "\n"
        "required_seats:\n"
        "  - id: operator\n"
        "    provides:\n"
        "      - single-task-execution\n"
        "\n"
        f"{step_key}:\n"
        "  - operator\n"
        "\n"
        "required_outputs:\n"
        "  - changed_files\n"
        "\n"
        "completion:\n"
        "  all_steps_pass: true\n"
    )


def _payload(step_key: str) -> dict:
    return {
        "schema": MISSION_SCHEMA,
        "id": "compat",
        "version": 1,
        "required_seats": [{"id": "operator", "provides": ["x"]}],
        step_key: ["operator"],
        "required_outputs": [],
        "completion": {},
    }


# --------------------------------------------------------------------------- #
# New field
# --------------------------------------------------------------------------- #

def test_execution_sequence_is_the_declared_field() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        mission = validate(_payload("execution_sequence"))
    assert mission.execution_sequence == ["operator"]


def test_shipped_missions_declare_execution_sequence() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        missions = load_all(REPO_ROOT)
    assert missions, "no missions loaded"
    for mission in missions:
        assert mission.execution_sequence, f"mission {mission.id} has no sequence"


def test_no_mission_file_still_uses_execution_graph() -> None:
    stale = [
        path.name
        for path in sorted((REPO_ROOT / "missions").glob("*.yaml"))
        if "execution_graph:" in path.read_text(encoding="utf-8")
    ]
    assert stale == []


# --------------------------------------------------------------------------- #
# Old field — loads, warns exactly once
# --------------------------------------------------------------------------- #

def test_legacy_execution_graph_still_validates_with_one_warning() -> None:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        mission = validate(_payload("execution_graph"))
    assert mission.execution_sequence == ["operator"]
    deprecations = [w for w in caught if issubclass(w.category, DeprecationWarning)]
    assert len(deprecations) == 1, [str(w.message) for w in deprecations]
    assert "execution_sequence" in str(deprecations[0].message)


def test_legacy_mission_file_loads_with_one_warning(tmp_path: Path) -> None:
    path = tmp_path / "legacy.yaml"
    path.write_text(_mission_body("execution_graph"), encoding="utf-8")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        mission = load(path)
    assert mission.execution_sequence == ["operator"]
    deprecations = [w for w in caught if issubclass(w.category, DeprecationWarning)]
    assert len(deprecations) == 1, [str(w.message) for w in deprecations]


def test_new_mission_file_loads_without_warning(tmp_path: Path) -> None:
    path = tmp_path / "new.yaml"
    path.write_text(_mission_body("execution_sequence"), encoding="utf-8")
    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        assert load(path).execution_sequence == ["operator"]


def test_missing_both_field_names_is_a_schema_error() -> None:
    payload = _payload("execution_sequence")
    del payload["execution_sequence"]
    with pytest.raises(MissionSchemaError):
        validate(payload)


def test_declaring_both_field_names_is_a_schema_error() -> None:
    payload = _payload("execution_sequence")
    payload["execution_graph"] = ["operator"]
    with pytest.raises(MissionSchemaError):
        validate(payload)


# --------------------------------------------------------------------------- #
# The rename reaches the compiled plan
# --------------------------------------------------------------------------- #

def test_compiled_plan_serialises_execution_sequence() -> None:
    from shiroe.teams.plan import CompiledTeamPlan

    plan = CompiledTeamPlan(
        run_id="r", task_id="t", mission_id="m", policy_id="p",
        active_harness="h", execution_sequence=["operator"],
    )
    payload = plan.to_dict()
    assert payload["execution_sequence"] == ["operator"]
    assert "execution_graph" not in payload
