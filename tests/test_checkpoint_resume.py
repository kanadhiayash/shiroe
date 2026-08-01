"""
privacy-audit: allow-file "Tests reference run-directory field names and fixture text only; no user data."

Checkpoint / resume behaviour for long scored runs.

A full external campaign on local hardware runs for days and will be
interrupted. These tests pin the three properties that make an interrupted
run recoverable rather than wasted.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from benchmarks.external.checkpoint import (  # noqa: E402
    CheckpointMismatchError,
    CheckpointStore,
)
from benchmarks.external.judges.fake import DeterministicFakeJudge  # noqa: E402
from benchmarks.external.providers.base import Completion, Provider, Usage  # noqa: E402
from benchmarks.external.runner import run_three_arms  # noqa: E402

LOCOMO_DIR = REPO / "benchmarks" / "external" / "fixtures" / "locomo"


class CountingProvider(Provider):
    """Dry-run provider that counts how many completions were generated."""

    name = "counting"
    model_id = "counting-1"

    def __init__(self) -> None:
        self.calls = 0
        self.dry_run = True
        self.total_input_tokens = 0
        self.total_output_tokens = 0

    def estimate(self, prompt: str, expected_output_tokens: int = 256) -> Usage:
        return Usage(input_tokens=1, output_tokens=1, cost_usd=0.0, estimated=True)

    def complete(self, prompt: str) -> Completion:
        self.calls += 1
        self.total_input_tokens += 1
        self.total_output_tokens += 1
        return Completion(text="an answer", usage=self.estimate(prompt))


def _run(run_dir: Path, provider: Provider):
    return run_three_arms(
        "locomo", LOCOMO_DIR, arms="all", scored=True, provider=provider,
        judge=DeterministicFakeJudge(), max_cost=500.0, checkpoint_dir=run_dir,
    )


def test_resume_replays_instead_of_regenerating(tmp_path: Path) -> None:
    """The point of a checkpoint: never pay for the same case twice."""
    run_dir = tmp_path / "run"

    first_provider = CountingProvider()
    first = _run(run_dir, first_provider)
    assert first["resumed_task_count"] == 0
    assert first_provider.calls > 0

    second_provider = CountingProvider()
    second = _run(run_dir, second_provider)
    assert second_provider.calls == 0, "resume regenerated already-completed cases"
    assert second["resumed_task_count"] == first_provider.calls

    for arm in first["results_by_arm"]:
        assert (
            second["results_by_arm"][arm]["judge_accuracy"]
            == first["results_by_arm"][arm]["judge_accuracy"]
        )


def test_resume_after_truncated_write_drops_only_the_partial_line(tmp_path: Path) -> None:
    """A process killed mid-write must not make the run unresumable."""
    run_dir = tmp_path / "run"
    _run(run_dir, CountingProvider())

    records = run_dir / "records.jsonl"
    intact = records.read_text(encoding="utf-8").splitlines()
    records.write_text("\n".join(intact) + '\n{"task_id": "half', encoding="utf-8")

    store = CheckpointStore(run_dir)
    assert len(store.completed()) == len(intact)

    provider = CountingProvider()
    resumed = _run(run_dir, provider)
    assert provider.calls == 0
    assert resumed["resumed_task_count"] == len(intact)


def test_resume_refuses_a_changed_configuration(tmp_path: Path) -> None:
    """Merging two configurations into one set of numbers is the defect."""
    run_dir = tmp_path / "run"
    store = CheckpointStore(run_dir)
    store.bind({"benchmark": "locomo", "seed": 0, "provider_model": "model-a"})

    other = CheckpointStore(run_dir)
    with pytest.raises(CheckpointMismatchError) as excinfo:
        other.bind({"benchmark": "locomo", "seed": 0, "provider_model": "model-b"})
    assert "model-a" in str(excinfo.value) and "model-b" in str(excinfo.value)


def test_records_are_durable_per_case(tmp_path: Path) -> None:
    """Each record is flushed and fsynced before the next call begins."""
    store = CheckpointStore(tmp_path / "run")
    store.bind({"benchmark": "x"})
    store.append({"task_id": "t1", "arm": "shiroe", "official_score": 1.0})
    # Read from a separate handle without closing the writer.
    reread = CheckpointStore(tmp_path / "run").completed()
    assert len(reread) == 1
    store.close()


def test_incomplete_scored_run_withholds_means(tmp_path: Path) -> None:
    """A verdict computed from partial data is not a result."""
    class FailingProvider(CountingProvider):
        def complete(self, prompt: str) -> Completion:
            raise RuntimeError("provider exploded")

    payload = run_three_arms(
        "locomo", LOCOMO_DIR, arms="all", scored=True, provider=FailingProvider(),
        judge=DeterministicFakeJudge(), max_cost=500.0,
    )
    assert payload["complete"] is False
    assert payload["failure_count"] > 0
    for arm_result in payload["results_by_arm"].values():
        assert arm_result["judge_accuracy"] is None
        assert arm_result["official_metric_mean"] is None
        assert "metrics_withheld_reason" in arm_result
        # Retrieval proxy does not depend on a call succeeding, so it survives.
        assert arm_result["retrieval_hit_proxy_mean"] is not None


def test_complete_run_reports_means(tmp_path: Path) -> None:
    payload = run_three_arms(
        "locomo", LOCOMO_DIR, arms="all", scored=True, provider=CountingProvider(),
        judge=DeterministicFakeJudge(), max_cost=500.0,
    )
    assert payload["complete"] is True
    assert payload["failure_count"] == 0
    for arm_result in payload["results_by_arm"].values():
        assert arm_result["judge_accuracy"] is not None
        assert "metrics_withheld_reason" not in arm_result


def test_header_records_run_identity(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    _run(run_dir, CountingProvider())
    header = json.loads((run_dir / "run-header.json").read_text(encoding="utf-8"))
    for field in ("benchmark", "arms", "seed", "chunk_target_chars",
                  "prompt_template_sha256", "provider_model", "judge_model"):
        assert field in header
