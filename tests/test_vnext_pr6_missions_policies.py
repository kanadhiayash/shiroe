"""vNext PR 6 gate tests — missions + execution policies."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from shiroe import execution_policies as ep
from shiroe import missions as ms
from shiroe.execution_policies.schema import POLICY_IDS, PolicySchemaError, validate as validate_policy
from shiroe.missions.schema import MISSION_SCHEMA, MissionSchemaError, validate as validate_mission
from shiroe.yaml_subset import YAMLSubsetError, parse

REPO_ROOT = Path(__file__).resolve().parents[1]

_MISSION_IDS = ("solo", "build", "research", "red", "audit", "ship")


# ---------------------------------------------------------------------------
# YAML subset parser
# ---------------------------------------------------------------------------

def test_yaml_subset_parses_scalars() -> None:
    got = parse("x: 1\ny: hello\nz: true\nq: 3.5\nn: null\n")
    assert got == {"x": 1, "y": "hello", "z": True, "q": 3.5, "n": None}


def test_yaml_subset_parses_nested_mapping() -> None:
    got = parse("root:\n  a: 1\n  b: 2\n")
    assert got == {"root": {"a": 1, "b": 2}}


def test_yaml_subset_parses_sequence_of_scalars() -> None:
    got = parse("items:\n  - a\n  - b\n  - c\n")
    assert got == {"items": ["a", "b", "c"]}


def test_yaml_subset_parses_sequence_of_maps() -> None:
    got = parse("seats:\n  - id: planner\n    provides:\n      - plan\n  - id: doer\n    provides:\n      - do\n")
    assert got == {"seats": [
        {"id": "planner", "provides": ["plan"]},
        {"id": "doer", "provides": ["do"]},
    ]}


def test_yaml_subset_rejects_flow_style() -> None:
    with pytest.raises(YAMLSubsetError):
        parse("items: [a, b]\n")


def test_yaml_subset_rejects_tab_indent() -> None:
    with pytest.raises(YAMLSubsetError):
        parse("root:\n\tchild: 1\n")


# ---------------------------------------------------------------------------
# Missions on disk
# ---------------------------------------------------------------------------

def test_all_missions_present_and_schema_valid() -> None:
    loaded = {m.id: m for m in ms.load_all(REPO_ROOT)}
    for mid in _MISSION_IDS:
        assert mid in loaded, f"missing mission {mid!r}"
    for m in loaded.values():
        assert m.version == 1
        assert m.execution_sequence
        for seat in m.required_seats:
            assert seat.get("provides"), f"seat {seat.get('id')} lacks provides"


def test_execution_sequence_is_acyclic_and_covered() -> None:
    for m in ms.load_all(REPO_ROOT):
        seat_ids = {s["id"] for s in m.required_seats}
        # every sequence step must map to a seat (already checked in schema
        # validator) and there must be no duplicates
        assert len(m.execution_sequence) == len(set(m.execution_sequence)), \
            f"mission {m.id} execution_sequence has duplicates"
        assert set(m.execution_sequence) <= seat_ids


def test_independence_declarations_are_valid() -> None:
    build = ms.get_mission(REPO_ROOT, "build")
    verifier = next(s for s in build.required_seats if s["id"] == "verifier")
    assert verifier["constraints"]["independent_from"] == ["implementer"]


def test_mission_schema_rejects_missing_provides() -> None:
    bad = {
        "schema": MISSION_SCHEMA, "id": "bad", "version": 1,
        "required_seats": [{"id": "x"}],
        "execution_sequence": ["x"],
        "required_outputs": [], "completion": {},
    }
    with pytest.raises(MissionSchemaError):
        validate_mission(bad)


def test_mission_schema_rejects_sequence_step_not_in_seats() -> None:
    bad = {
        "schema": MISSION_SCHEMA, "id": "bad", "version": 1,
        "required_seats": [{"id": "a", "provides": ["x"]}],
        "execution_sequence": ["a", "ghost"],
        "required_outputs": [], "completion": {},
    }
    with pytest.raises(MissionSchemaError):
        validate_mission(bad)


# ---------------------------------------------------------------------------
# No hardcoded model / capability ids in missions — PR 6 gate
# ---------------------------------------------------------------------------

_MODEL_PATTERN = re.compile(
    r"claude-(?:opus|sonnet|haiku|fable|instant)"
    r"|gpt-[0-9]|gemini-[0-9]|codex-gpt"
)
_CAP_ID_PATTERN = re.compile(r"^\s*capability:\s*[\w:-]+", re.MULTILINE)


def test_missions_contain_no_hardcoded_model_ids() -> None:
    missions_dir = REPO_ROOT / "missions"
    for p in missions_dir.glob("*.yaml"):
        text = p.read_text(encoding="utf-8")
        m = _MODEL_PATTERN.search(text)
        assert m is None, f"{p.name} contains model id {m.group(0)!r}"


def test_missions_do_not_pin_capability_ids() -> None:
    missions_dir = REPO_ROOT / "missions"
    for p in missions_dir.glob("*.yaml"):
        text = p.read_text(encoding="utf-8")
        m = _CAP_ID_PATTERN.search(text)
        assert m is None, f"{p.name} pins a capability id: {m.group(0)!r}"


# ---------------------------------------------------------------------------
# Policies
# ---------------------------------------------------------------------------

def test_all_policies_present_and_schema_valid() -> None:
    loaded = {p.id: p for p in ep.load_all(REPO_ROOT)}
    for pid in POLICY_IDS:
        assert pid in loaded


def test_policy_worker_ordering() -> None:
    by_id = {p.id: p for p in ep.load_all(REPO_ROOT)}
    assert by_id["lean"].max_parallel_workers \
        <= by_id["balanced"].max_parallel_workers \
        <= by_id["assured"].max_parallel_workers


def test_policy_capability_cap_ordering() -> None:
    by_id = {p.id: p for p in ep.load_all(REPO_ROOT)}
    assert by_id["lean"].max_capabilities \
        <= by_id["balanced"].max_capabilities \
        <= by_id["assured"].max_capabilities


def test_frontier_reasoning_is_gated_by_policy() -> None:
    by_id = {p.id: p for p in ep.load_all(REPO_ROOT)}
    # lean / balanced explicitly deny frontier; assured caps it
    assert by_id["lean"].reasoning_class_limits["frontier"] == 0
    assert by_id["balanced"].reasoning_class_limits["frontier"] == 0
    assert by_id["assured"].reasoning_class_limits["frontier"] > 0


def test_policy_schema_rejects_bad_autonomy() -> None:
    with pytest.raises(PolicySchemaError):
        validate_policy({
            "schema": "shiroe.policy/v1", "id": "lean", "version": 1,
            "max_parallel_workers": 1, "max_capabilities": 1,
            "independent_verifiers": 0, "autonomy_default": "chaos",
            "reasoning_class_limits": {"fast": 1, "balanced": 1, "deep": 0, "frontier": 0},
            "cost_envelope": {"usd_max": 0.1, "tokens_input_max": 1, "tokens_output_max": 1},
        })


def test_policy_schema_rejects_unknown_id() -> None:
    with pytest.raises(PolicySchemaError):
        validate_policy({
            "schema": "shiroe.policy/v1", "id": "not-a-policy", "version": 1,
            "max_parallel_workers": 1, "max_capabilities": 1,
            "independent_verifiers": 0, "autonomy_default": "auto-safe",
            "reasoning_class_limits": {"fast": 1, "balanced": 1, "deep": 0, "frontier": 0},
            "cost_envelope": {"usd_max": 0.1, "tokens_input_max": 1, "tokens_output_max": 1},
        })
