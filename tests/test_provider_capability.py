"""ZRF-60: provider capability registry — fail-closed model verification.

Before this ticket, ``JsonProviderAdapter`` validated only the ``schema``
string and that class keys were known reasoning classes; any ``model_id``
string resolved, invented or retired alike (the RED-FIRST defect captured
in ``docs/_evidence/ZRF-60/baseline.txt``). This suite locks in the fix:
schema v2 lifecycle/verification, fail-closed live-call resolution, v1
back-compat as unverified, single-level fallback that never changes what
the gateway granted, and a refresh command that only ever writes fields it
actually confirmed.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from zeref.adapters.providers import available_providers, get_provider, resolve_model
from zeref.adapters.providers.base import (
    PROVIDER_SCHEMA_V1,
    PROVIDER_SCHEMA_V2,
    JsonProviderAdapter,
)
from zeref.adapters.providers.refresh import (
    STALE_ON_REFRESH,
    _apply_refresh,
    _lifecycle_from_presence,
    refresh_provider,
)
from zeref.core.reasoning import ReasoningPolicyError
from zeref.routing.gateway import ModelCallRequest, RoutingError, route
from zeref.security import ConnectorDisabledError

REPO = Path(__file__).resolve().parents[1]


def _write(tmp_path: Path, name: str, data: dict) -> Path:
    p = tmp_path / name
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


def _v2_entry(**overrides) -> dict:
    base = {
        "model_id": "widget-1",
        "lifecycle": "active",
        "source_url": "https://example.test/docs",
        "verified_at": "2026-07-27",
        "verified_by": "human",
    }
    base.update(overrides)
    return base


# --- the regression: an invented model_id must not resolve on a live path --


def test_fake_model_id_rejected_on_live_path(tmp_path: Path) -> None:
    """RED-FIRST baseline: this exact fixture used to resolve successfully."""
    fixture = {
        "schema": PROVIDER_SCHEMA_V1,
        "provider": "fake",
        "classes": {"fast": {"model_id": "definitely-not-a-real-model"}},
    }
    path = _write(tmp_path, "fake.json", fixture)
    adapter = JsonProviderAdapter(path)
    with pytest.raises(ReasoningPolicyError):
        adapter.resolve("fast", live=True)


def test_fake_model_id_proceeds_with_warning_on_dry_run(tmp_path: Path) -> None:
    fixture = {
        "schema": PROVIDER_SCHEMA_V1,
        "provider": "fake",
        "classes": {"fast": {"model_id": "definitely-not-a-real-model"}},
    }
    path = _write(tmp_path, "fake.json", fixture)
    adapter = JsonProviderAdapter(path)
    spec = adapter.resolve("fast", live=False)
    assert spec.model_id == "definitely-not-a-real-model"
    assert spec.verified is False
    assert spec.warning is not None and "dry-run" in spec.warning


# --- v1 back-compat: still loads, treated as unverified ---------------------


def test_v1_file_still_loads(tmp_path: Path) -> None:
    fixture = {
        "schema": PROVIDER_SCHEMA_V1,
        "provider": "legacy",
        "classes": {"fast": {"model_id": "some-model", "effort": "low"}},
    }
    path = _write(tmp_path, "legacy.json", fixture)
    adapter = JsonProviderAdapter(path)
    assert adapter.schema == PROVIDER_SCHEMA_V1
    cap = adapter.capability("fast")
    assert cap.verified is False
    assert cap.lifecycle == "unknown"


def test_v1_entries_fail_closed_on_live_even_with_plausible_model_id(tmp_path: Path) -> None:
    """A v1 entry with a perfectly ordinary-looking model id is still
    unverified — v1 carries no verification metadata at all."""
    fixture = {
        "schema": PROVIDER_SCHEMA_V1,
        "provider": "legacy",
        "classes": {"balanced": {"model_id": "gpt-4o"}},
    }
    path = _write(tmp_path, "legacy.json", fixture)
    adapter = JsonProviderAdapter(path)
    with pytest.raises(ReasoningPolicyError, match="verified=False"):
        adapter.resolve("balanced", live=True)


# --- v2: lifecycle fail-closed matrix ----------------------------------------


@pytest.mark.parametrize("lifecycle", ["deprecated", "retired", "unknown"])
def test_non_active_lifecycle_fails_closed_on_live(tmp_path: Path, lifecycle: str) -> None:
    fixture = {
        "schema": PROVIDER_SCHEMA_V2,
        "provider": "p",
        "classes": {"fast": _v2_entry(lifecycle=lifecycle)},
    }
    path = _write(tmp_path, "p.json", fixture)
    adapter = JsonProviderAdapter(path)
    with pytest.raises(ReasoningPolicyError):
        adapter.resolve("fast", live=True)


def test_active_but_unverified_fails_closed_on_live(tmp_path: Path) -> None:
    """lifecycle=active alone is not enough — verified_at/verified_by must
    both be present, or the model is still unverified."""
    fixture = {
        "schema": PROVIDER_SCHEMA_V2,
        "provider": "p",
        "classes": {"fast": _v2_entry(verified_at=None, verified_by=None)},
    }
    path = _write(tmp_path, "p.json", fixture)
    adapter = JsonProviderAdapter(path)
    with pytest.raises(ReasoningPolicyError, match="verified=False"):
        adapter.resolve("fast", live=True)


def test_active_verified_model_resolves(tmp_path: Path) -> None:
    fixture = {
        "schema": PROVIDER_SCHEMA_V2,
        "provider": "p",
        "classes": {"fast": _v2_entry()},
    }
    path = _write(tmp_path, "p.json", fixture)
    adapter = JsonProviderAdapter(path)
    spec = adapter.resolve("fast", live=True)
    assert spec.model_id == "widget-1"
    assert spec.verified is True
    assert spec.lifecycle == "active"
    assert spec.warning is None


def test_invalid_lifecycle_value_rejected_at_load(tmp_path: Path) -> None:
    fixture = {
        "schema": PROVIDER_SCHEMA_V2,
        "provider": "p",
        "classes": {"fast": _v2_entry(lifecycle="ancient")},
    }
    path = _write(tmp_path, "p.json", fixture)
    with pytest.raises(ValueError, match="lifecycle"):
        JsonProviderAdapter(path)


# --- fallback: never upgrades or downgrades what the gateway granted --------


def test_fallback_used_when_primary_fails_closed_live(tmp_path: Path, monkeypatch) -> None:
    fixture = {
        "schema": PROVIDER_SCHEMA_V2,
        "provider": "p",
        "classes": {
            "deep": _v2_entry(
                model_id="widget-deep-old",
                lifecycle="deprecated",
                fallback=_v2_entry(model_id="widget-deep-new"),
            )
        },
    }
    path = _write(tmp_path, "p.json", fixture)
    adapter = JsonProviderAdapter(path)
    spec = adapter.resolve("deep", live=True)
    assert spec.model_id == "widget-deep-new"
    assert spec.reasoning_class == "deep"  # class label is untouched
    assert spec.warning is not None and "fallback" in spec.warning


def test_fallback_does_not_chain(tmp_path: Path) -> None:
    """A fallback that is itself unverified/deprecated must not cascade to
    a second fallback — one level only, then fail closed."""
    fixture = {
        "schema": PROVIDER_SCHEMA_V2,
        "provider": "p",
        "classes": {
            "deep": _v2_entry(
                lifecycle="deprecated",
                fallback=_v2_entry(model_id="also-bad", lifecycle="retired"),
            )
        },
    }
    path = _write(tmp_path, "p.json", fixture)
    adapter = JsonProviderAdapter(path)
    with pytest.raises(ReasoningPolicyError):
        adapter.resolve("deep", live=True)


def test_fallback_preserves_gateway_entitlement_placement_and_privacy(
    tmp_path: Path, monkeypatch
) -> None:
    """The gateway granted HIGH -> 'deep' with placement=any, privacy=
    confidential. A primary-model fallback must land the call on a
    different concrete model without silently changing any of that."""
    fixture = {
        "schema": PROVIDER_SCHEMA_V2,
        "provider": "fallbacktest",
        "classes": {
            "deep": _v2_entry(
                model_id="deep-old",
                lifecycle="retired",
                fallback=_v2_entry(model_id="deep-new"),
            )
        },
    }
    _write(tmp_path, "fallbacktest.json", fixture)
    monkeypatch.setattr("zeref.adapters.providers._PKG_DIR", tmp_path)
    monkeypatch.setattr("zeref.adapters.providers._cache", {})

    decision = route(ModelCallRequest(
        criticality="HIGH", purpose="fallback preserves entitlement",
        placement="any", privacy_class="confidential", provider="fallbacktest",
    ))
    assert decision.entitled_class == "deep"
    assert decision.reasoning_class == "deep"
    assert decision.placement == "any"
    assert decision.privacy_class == "confidential"
    assert decision.model_spec.model_id == "deep-new"


# --- refresh: only ever writes what it actually confirmed -------------------


def test_lifecycle_from_presence_matrix() -> None:
    assert _lifecycle_from_presence("unknown", present=True) == "active"
    assert _lifecycle_from_presence("active", present=True) == "active"
    # presence never un-deprecates — still listed is not still current
    assert _lifecycle_from_presence("deprecated", present=True) == "deprecated"
    assert _lifecycle_from_presence("active", present=False) == "retired"
    assert _lifecycle_from_presence("unknown", present=False) == "retired"


def test_refresh_never_writes_verified_at_for_an_unconfirmed_field() -> None:
    data = {
        "schema": PROVIDER_SCHEMA_V2,
        "provider": "p",
        "classes": {
            "fast": {
                "model_id": "widget-1",
                "lifecycle": "unknown",
                "verified_at": None,
                "verified_by": None,
                "context_window": None,
                "max_output_tokens": None,
                "endpoint": None,
                "modalities": [],
                "supports_tools": None,
                "supports_structured_output": None,
                "region": None,
                "retention_class": None,
            },
        },
    }
    changed = _apply_refresh(data, ids={"widget-1"}, url="https://api.test/v1/models",
                              digest="deadbeef", checked_at="2026-07-27")
    entry = data["classes"]["fast"]
    assert len(changed) == 1
    assert entry["lifecycle"] == "active"
    assert entry["verified_at"] == "2026-07-27"
    assert entry["verified_by"] == "api"
    # refresh is machine-confirmed existence only — every field with no
    # machine-readable source stays exactly as it was, not guessed.
    assert entry["context_window"] is None
    assert entry["max_output_tokens"] is None
    assert entry["supports_tools"] is None
    for f in STALE_ON_REFRESH:
        assert f in entry  # present but untouched


def test_refresh_does_not_touch_an_entry_with_no_new_evidence() -> None:
    """Already-active, still-present: nothing changed, so refresh must not
    re-stamp verified_at — that would be re-confirming something it did not
    actually re-check."""
    data = {
        "schema": PROVIDER_SCHEMA_V2,
        "provider": "p",
        "classes": {
            "fast": _v2_entry(model_id="widget-1", verified_at="2020-01-01", verified_by="human"),
        },
    }
    changed = _apply_refresh(data, ids={"widget-1"}, url="https://api.test/v1/models",
                              digest="deadbeef", checked_at="2026-07-27")
    assert changed == []
    assert data["classes"]["fast"]["verified_at"] == "2020-01-01"
    assert data["classes"]["fast"]["verified_by"] == "human"


def test_refresh_marks_absent_model_retired() -> None:
    data = {
        "schema": PROVIDER_SCHEMA_V2,
        "provider": "p",
        "classes": {"fast": _v2_entry(model_id="widget-gone")},
    }
    changed = _apply_refresh(data, ids=set(), url="https://api.test/v1/models",
                              digest="deadbeef", checked_at="2026-07-27")
    assert changed[0]["lifecycle"] == {"from": "active", "to": "retired"}
    assert data["classes"]["fast"]["lifecycle"] == "retired"
    assert data["classes"]["fast"]["verified_by"] == "api"


def test_refresh_rejects_v1_schema() -> None:
    data = {"schema": PROVIDER_SCHEMA_V1, "provider": "p",
            "classes": {"fast": {"model_id": "x"}}}
    with pytest.raises(ValueError, match="v2"):
        _apply_refresh(data, ids={"x"}, url="u", digest="d", checked_at="2026-07-27")


def test_refresh_command_is_off_by_default_and_hits_no_network() -> None:
    """The connector gate must refuse before any network call — this is
    what keeps `zeref providers refresh` off in CI and silent in the test
    suite. No env override is set here, and SHARING_POLICY.md ships
    provider_refresh: enabled: false."""
    with pytest.raises(ConnectorDisabledError):
        refresh_provider("anthropic", project_root=REPO)


# --- real registry files: verified mappings resolve; unverified ones don't --


def test_anthropic_registry_is_v2_and_fully_verified() -> None:
    adapter = get_provider("anthropic")
    assert adapter.schema == PROVIDER_SCHEMA_V2
    for cls in adapter.supported_classes():
        cap = adapter.capability(cls)
        assert cap.lifecycle == "active"
        assert cap.verified is True
        spec = resolve_model(cls, provider="anthropic", live=True)
        assert spec.warning is None


def test_openai_deep_mapping_is_honestly_unverified_not_fabricated() -> None:
    """codex-gpt-5-5 could not be confirmed against official docs (PART B) —
    it must be lifecycle=unknown/unverified, and must fail closed live,
    never silently resolved."""
    adapter = get_provider("openai")
    cap = adapter.capability("deep")
    assert cap.lifecycle == "unknown"
    assert cap.verified is False
    with pytest.raises(ReasoningPolicyError):
        resolve_model("deep", provider="openai", live=True)


def test_openai_balanced_mapping_is_deprecated_and_fails_closed() -> None:
    """gpt-4o was confirmed deprecated against official docs (PART B)."""
    adapter = get_provider("openai")
    cap = adapter.capability("balanced")
    assert cap.lifecycle == "deprecated"
    assert cap.verified is True  # the deprecation itself was confirmed
    with pytest.raises(ReasoningPolicyError):
        resolve_model("balanced", provider="openai", live=True)


def test_openai_fast_mapping_is_active_and_resolves() -> None:
    adapter = get_provider("openai")
    cap = adapter.capability("fast")
    assert cap.lifecycle == "active"
    assert cap.verified is True
    spec = resolve_model("fast", provider="openai", live=True)
    assert spec.model_id == "gpt-4o-mini"


# --- evidence artifact: capability / lifecycle / fallback matrix ------------


def test_capability_matrix_is_recorded_as_pr_evidence() -> None:
    """Not a correctness assertion by itself — this is the PR's evidence
    artifact: a human-readable table of every provider/class mapping this
    ticket touched, its lifecycle, verification, and fallback, written
    under the gitignored docs/_evidence/ so it ships with the PR
    description rather than the repo."""
    rows: list[str] = []
    header = f"{'provider':<10} {'class':<10} {'model_id':<24} {'lifecycle':<11} {'verified':<9} {'fallback'}"
    rows.append(header)
    rows.append("-" * len(header))
    for provider in available_providers():
        adapter = get_provider(provider)
        for cls in sorted(adapter.supported_classes()):
            cap = adapter.capability(cls)
            fb = adapter._classes[cls].get("fallback")
            fb_desc = fb["model_id"] if fb else "-"
            model_id = adapter._classes[cls]["model_id"]
            rows.append(
                f"{provider:<10} {cls:<10} {model_id:<24} {cap.lifecycle:<11} "
                f"{str(cap.verified):<9} {fb_desc}"
            )
    matrix = "\n".join(rows) + "\n"

    out_dir = REPO / "docs" / "_evidence" / "ZRF-60"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "capability_matrix.txt").write_text(matrix, encoding="utf-8")
    print("\n" + matrix)

    assert "anthropic" in matrix
    assert "openai" in matrix
    assert "unknown" in matrix  # codex-gpt-5-5 shows up honestly unverified
    assert "deprecated" in matrix  # gpt-4o shows up honestly deprecated
