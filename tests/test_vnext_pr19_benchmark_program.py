"""vNext PR 19 gate tests — external benchmark program."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from shiroe.benchmark.program import (
    ArtifactValidationError,
    BenchmarkArtifact,
    BenchmarkCategory,
    Classification,
    list_benchmarks,
    run_benchmark,
    validate_artifact,
    write_artifact,
)
from shiroe.benchmark.program.artifact import new_id, sha256_of


# ---------------------------------------------------------------------------
# Artifact schema — §16.10 gate
# ---------------------------------------------------------------------------

def _artifact_kwargs(**overrides) -> dict:
    base = dict(
        id=new_id(), category="conformance",
        name="conformance/example", shiroe_version="2.0.0-alpha.1",
        shiroe_commit="deadbeef", harness="claude-code",
        harness_version="1.2.3",
        model_or_provider="fast:haiku",
        dataset_version="fixture-v1", configuration={},
        seed=42, runs=1, mean=1.0, variance=0.0,
        failures=0, abstentions=0,
        raw_artifact_hash=sha256_of("payload"),
        classification="fixture",
    )
    base.update(overrides)
    return base


def test_artifact_validates_required_fields() -> None:
    d = _artifact_kwargs()
    d["schema"] = "shiroe.benchmark-artifact/v1"
    validate_artifact(d)


def test_artifact_rejects_missing_required() -> None:
    d = _artifact_kwargs()
    d.pop("harness")
    d["schema"] = "shiroe.benchmark-artifact/v1"
    with pytest.raises(ArtifactValidationError):
        validate_artifact(d)


def test_artifact_rejects_bad_classification() -> None:
    d = _artifact_kwargs(classification="propaganda")
    d["schema"] = "shiroe.benchmark-artifact/v1"
    with pytest.raises(ArtifactValidationError):
        validate_artifact(d)


def test_artifact_requires_sha256_prefix() -> None:
    d = _artifact_kwargs(raw_artifact_hash="notprefixed")
    d["schema"] = "shiroe.benchmark-artifact/v1"
    with pytest.raises(ArtifactValidationError):
        validate_artifact(d)


def test_write_artifact_persists_to_benchmarks_artifacts(tmp_path: Path) -> None:
    art = BenchmarkArtifact(**_artifact_kwargs())
    target = write_artifact(tmp_path, art)
    assert target.parent == tmp_path / "benchmarks" / "artifacts"
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["schema"] == "shiroe.benchmark-artifact/v1"
    assert payload["classification"] == "fixture"


# ---------------------------------------------------------------------------
# Registered benchmarks
# ---------------------------------------------------------------------------

def test_at_least_one_benchmark_per_key_category() -> None:
    benches = list_benchmarks()
    categories = {b["category"] for b in benches}
    for required in ("conformance", "capability_resolver", "codec",
                     "security", "evidence"):
        assert required in categories, f"missing benchmark for category {required!r}"


def test_run_conformance_state_transitions_passes() -> None:
    result = run_benchmark("conformance/state-transitions")
    assert result.mean == 1.0
    assert result.failures == 0
    assert result.classification is Classification.fixture


def test_run_policy_monotonicity_zero_violations() -> None:
    result = run_benchmark("security/policy-monotonicity")
    assert result.failures == 0
    assert result.metadata["violations"] == 0


def test_run_evidence_robustness_gate_holds() -> None:
    result = run_benchmark("evidence/robustness-cannot-upgrade")
    assert result.mean == 1.0
    assert result.metadata["final_grade"] == "weak"


def test_run_codec_roundtrip_succeeds() -> None:
    result = run_benchmark("codec/round-trip")
    assert result.mean == 1.0
    assert result.failures == 0


def test_run_benchmark_unknown_raises() -> None:
    with pytest.raises(KeyError):
        run_benchmark("nonexistent/bench")


# ---------------------------------------------------------------------------
# End-to-end: run + persist an artifact
# ---------------------------------------------------------------------------

def test_benchmark_result_wraps_into_valid_artifact(tmp_path: Path) -> None:
    result = run_benchmark("conformance/state-transitions")
    art = BenchmarkArtifact(
        id=new_id(), category=result.category.value,
        name=result.name, shiroe_version="2.0.0-alpha.1",
        shiroe_commit="deadbeef", harness="claude-code",
        harness_version="1.2.3", model_or_provider="fast:haiku",
        dataset_version="fixture-v1", configuration={},
        seed=42, runs=result.runs, mean=result.mean,
        variance=result.variance, failures=result.failures,
        abstentions=result.abstentions,
        raw_artifact_hash=result.raw_artifact,
        classification=result.classification.value,
    )
    target = write_artifact(tmp_path, art)
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["mean"] == 1.0
    assert payload["failures"] == 0
