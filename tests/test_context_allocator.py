"""ZRF-64: context budget allocator.

packet.py renders six sections but owns no budget. These tests lock in the
fix: a hard budget derived from PR 2's provider capability registry, whole
records only (never sliced), mandatory sections that always survive or the
call refuses outright, and an omission manifest that accounts for every
dropped record.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from zeref.adapters.providers.base import JsonProviderAdapter, ModelCapability
from zeref.context.allocator import AllocatorError, allocate_packet

REPO = Path(__file__).resolve().parents[1]


def _capability(**overrides) -> ModelCapability:
    base = dict(
        lifecycle="active",
        verified_at="2026-07-27",
        verified_by="human",
        context_window=100_000,
        max_output_tokens=8_000,
    )
    base.update(overrides)
    return ModelCapability(**base)


def _records(n: int, *, prefix: str = "r", kind: str | None = None, body: str = "x") -> list[dict]:
    out = []
    for i in range(n):
        rec = {"id": f"{prefix}{i}", "body": body}
        if kind is not None:
            rec["kind"] = kind
        out.append(rec)
    return out


BASE_KWARGS = dict(
    objective="Do the thing.",
    permissions={"read": True, "write": False},
)


# ---------------------------------------------------------------------------
# Matrix
# ---------------------------------------------------------------------------

def test_tiny_prompt_fits_with_no_omissions() -> None:
    result = allocate_packet(
        **BASE_KWARGS,
        memory_records=_records(2),
        evidence=_records(1),
        capability=_capability(),
    )
    assert result.packet.memory_records == _records(2)
    assert result.packet.evidence == _records(1)
    assert all(o.dropped_count == 0 for o in result.omissions)
    manifest = result.as_manifest()
    assert manifest["omissions"]


def test_memory_dominant_still_fits_evidence_when_possible() -> None:
    # Memory is huge, evidence is a single small record — evidence must not
    # starve just because memory rolled in first.
    memory = _records(400, body="x" * 200)
    evidence = _records(1, prefix="ev")
    result = allocate_packet(
        **BASE_KWARGS,
        memory_records=memory,
        evidence=evidence,
        capability=_capability(context_window=20_000, max_output_tokens=2_000),
    )
    assert result.packet.evidence == evidence
    ev_omission = next(o for o in result.omissions if o.section == "evidence")
    assert ev_omission.dropped_count == 0
    mem_omission = next(o for o in result.omissions if o.section == "memory")
    assert mem_omission.dropped_count > 0
    assert mem_omission.kept_count < len(memory)


def test_evidence_dominant_still_fits_memory_when_possible() -> None:
    evidence = _records(400, prefix="ev", body="x" * 200)
    memory = _records(1)
    result = allocate_packet(
        **BASE_KWARGS,
        memory_records=memory,
        evidence=evidence,
        capability=_capability(context_window=20_000, max_output_tokens=2_000),
    )
    assert result.packet.memory_records == memory
    mem_omission = next(o for o in result.omissions if o.section == "memory")
    assert mem_omission.dropped_count == 0
    ev_omission = next(o for o in result.omissions if o.section == "evidence")
    assert ev_omission.dropped_count > 0


def test_enormous_output_schema_triggers_refusal() -> None:
    huge_schema = {f"field_{i}": {"type": "string", "description": "x" * 500} for i in range(500)}
    with pytest.raises(AllocatorError):
        allocate_packet(
            **BASE_KWARGS,
            output_schema=huge_schema,
            capability=_capability(context_window=5_000, max_output_tokens=500),
        )


def test_mandatory_sections_exceed_budget_refuses() -> None:
    with pytest.raises(AllocatorError):
        allocate_packet(
            objective="x" * 5000,
            permissions={"read": True},
            capability=_capability(context_window=1_000, max_output_tokens=200),
        )


def test_small_model_context_forces_heavy_omission() -> None:
    memory = _records(200, body="x" * 100)
    evidence = _records(200, prefix="ev", body="x" * 100)
    result = allocate_packet(
        **BASE_KWARGS,
        memory_records=memory,
        evidence=evidence,
        capability=_capability(context_window=3_000, max_output_tokens=500),
    )
    total_kept = len(result.packet.memory_records) + len(result.packet.evidence)
    assert total_kept < len(memory) + len(evidence)
    assert any(o.dropped_count > 0 for o in result.omissions)
    # Nothing silent: every omission carries a record count and a reason.
    for o in result.omissions:
        assert isinstance(o.reason, str) and o.reason


def test_constraints_and_provenance_survive_before_generic_records() -> None:
    generic = _records(50, prefix="note", body="y" * 150)
    pinned = _records(5, prefix="pin", kind="constraint", body="z" * 150)
    provenance = _records(5, prefix="prov", kind="provenance", body="z" * 150)
    memory = generic + pinned + provenance
    result = allocate_packet(
        **BASE_KWARGS,
        memory_records=memory,
        capability=_capability(context_window=4_000, max_output_tokens=500),
    )
    kept_ids = {r["id"] for r in result.packet.memory_records}
    pinned_ids = {r["id"] for r in pinned}
    provenance_ids = {r["id"] for r in provenance}
    # All high-priority records survive; the budget was tight enough that
    # not every generic record could (proves ranking actually happened).
    assert pinned_ids <= kept_ids
    assert provenance_ids <= kept_ids
    assert len(kept_ids) < len(memory)


# ---------------------------------------------------------------------------
# Invariants
# ---------------------------------------------------------------------------

def test_no_record_is_ever_partially_included() -> None:
    memory = _records(100, body="x" * 80)
    result = allocate_packet(
        **BASE_KWARGS,
        memory_records=memory,
        capability=_capability(context_window=3_000, max_output_tokens=500),
    )
    by_id = {r["id"]: r for r in memory}
    for kept in result.packet.memory_records:
        assert kept == by_id[kept["id"]]


def test_mandatory_sections_always_present_when_allocation_succeeds() -> None:
    result = allocate_packet(
        objective="Objective text.",
        permissions={"a": 1},
        output_schema={"type": "object"},
        stop_rules="Stop when done.",
        memory_records=_records(50, body="x" * 100),
        capability=_capability(context_window=6_000, max_output_tokens=500),
    )
    for name in ("objective", "permissions", "output_schema", "stop_rules"):
        assert name in result.packet.sections


def test_input_plus_reserved_output_never_exceeds_context_window() -> None:
    cap = _capability(context_window=10_000, max_output_tokens=1_000)
    result = allocate_packet(
        **BASE_KWARGS,
        memory_records=_records(300, body="x" * 100),
        evidence=_records(300, prefix="ev", body="x" * 100),
        capability=cap,
    )
    assert result.budget.total_tokens + result.budget.output_reserve + result.budget.system_harness_reserve \
        + result.budget.safety_margin <= cap.context_window


def test_identical_input_yields_identical_allocation() -> None:
    memory = _records(30, body="x" * 90)
    evidence = _records(30, prefix="ev", body="x" * 90)
    cap = _capability(context_window=4_500, max_output_tokens=500)

    def run() -> tuple:
        result = allocate_packet(**BASE_KWARGS, memory_records=memory, evidence=evidence, capability=cap)
        return (
            result.packet.memory_records,
            result.packet.evidence,
            result.budget,
            [(o.section, o.kept_count, o.dropped_count) for o in result.omissions],
        )

    first = run()
    second = run()
    assert first == second


def test_missing_context_window_refuses_rather_than_guesses() -> None:
    with pytest.raises(AllocatorError):
        allocate_packet(**BASE_KWARGS, capability=_capability(context_window=None))


def test_missing_output_reserve_refuses_rather_than_guesses() -> None:
    with pytest.raises(AllocatorError):
        allocate_packet(**BASE_KWARGS, capability=_capability(max_output_tokens=None))


def test_output_reserve_override_bypasses_registry_value() -> None:
    result = allocate_packet(
        **BASE_KWARGS,
        capability=_capability(max_output_tokens=None),
        output_reserve=1_000,
    )
    assert result.budget.output_reserve == 1_000


# ---------------------------------------------------------------------------
# Registry integration (PR 2) — use a fixture provider file, not the real
# one, so this test doesn't drift if anthropic.json's numbers change.
# ---------------------------------------------------------------------------

def test_allocate_from_reasoning_class_uses_registry(tmp_path: Path) -> None:
    provider_json = tmp_path / "fixture.json"
    provider_json.write_text(json.dumps({
        "schema": "zeref.provider/v2",
        "provider": "fixture",
        "classes": {
            "fast": {
                "model_id": "fixture-fast",
                "lifecycle": "active",
                "source_url": "https://example.test/docs",
                "verified_at": "2026-07-27",
                "verified_by": "human",
                "context_window": 8_000,
                "max_output_tokens": 1_000,
            }
        },
    }), encoding="utf-8")
    adapter = JsonProviderAdapter(provider_json)
    cap = adapter.capability("fast")
    result = allocate_packet(**BASE_KWARGS, memory_records=_records(5), capability=cap)
    assert result.budget.context_window == 8_000
    assert result.budget.output_reserve == 1_000
