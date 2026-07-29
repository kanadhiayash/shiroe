"""
privacy-audit: allow-file "Tests reference env-var names and synthetic fixture text only; no user data."

WS5 Phase A — offline tests for the external benchmark harness.

No network, no API calls: loaders parse tiny synthetic committed fixtures,
the harness runs dry-run against the plain-files baseline, and results JSON
provenance is schema-checked.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from benchmarks.external.baselines.plain_files import PlainFilesBackend
from benchmarks.external.baselines.sqlite_store import SqliteFtsBackend
from benchmarks.external.harness import run_benchmark, token_f1, write_results
from benchmarks.external.loaders import LOADERS, get_loader
from benchmarks.external.providers.anthropic import AnthropicProvider
from benchmarks.external.schema import DatasetMissingError

FIXTURES = REPO / "benchmarks" / "external" / "fixtures"

LOADER_NAMES = sorted(LOADERS)


@pytest.mark.parametrize("name", LOADER_NAMES)
def test_loader_parses_fixture_to_common_schema(name: str) -> None:
    loader = get_loader(name)
    tasks = loader.load(FIXTURES / name)
    assert tasks, f"{name} fixture produced no tasks"
    assert len(tasks) <= 10, f"{name} fixture should stay tiny"
    for task in tasks:
        assert task.benchmark == name
        assert task.task_id
        assert isinstance(task.question, str) and task.question
        assert task.answers and all(isinstance(a, str) for a in task.answers)
        assert task.metric in {"exact_match", "token_f1", "choice_accuracy"}
        for session in task.sessions:
            for turn in session:
                assert isinstance(turn.role, str)
                assert isinstance(turn.content, str)


@pytest.mark.parametrize("name", LOADER_NAMES)
def test_loader_check_parses_fixture_dir(name: str) -> None:
    """The fixture must parse, and a hash must be reported.

    A loader with a PINNED_SHA256 will additionally report a checksum
    mismatch here, and that is correct: the pin identifies the real release,
    while the committed fixture is a small synthetic stand-in that must never
    equal it. So the mismatch is tolerated, but any OTHER error is a failure,
    and parsing must still succeed.
    """
    loader = get_loader(name)
    result = loader.check(FIXTURES / name)
    assert result.task_count > 0
    assert result.sha256_actual or getattr(loader, "PINNED_SHA256", None) is None
    non_checksum = [e for e in result.errors if "checksum mismatch" not in e]
    assert not non_checksum, non_checksum
    if getattr(loader, "PINNED_SHA256", None) is None:
        assert result.ok, result.errors


def test_pin_rejects_data_that_is_not_the_pinned_release(tmp_path: Path) -> None:
    """A pin that never fails is decoration.

    Point a pinned loader at a well-formed file whose bytes differ from the
    pinned release and the check must refuse it — that is the whole purpose
    of recording the hash before a scored run.
    """
    from benchmarks.external.loaders import locomo

    assert locomo.PINNED_SHA256, "locomo should be pinned"
    target = tmp_path / locomo.DATA_FILENAME
    target.write_text(
        (FIXTURES / "locomo" / locomo.DATA_FILENAME).read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    result = locomo.check(tmp_path)
    assert not result.ok
    assert any("checksum mismatch" in e for e in result.errors)


@pytest.mark.parametrize("name", LOADER_NAMES)
def test_loader_check_names_manual_download_when_missing(name: str, tmp_path: Path) -> None:
    loader = get_loader(name)
    result = loader.check(tmp_path / "empty")
    assert not result.ok
    message = " ".join(result.errors)
    assert loader.OFFICIAL_URL in message
    assert "Manual download" in message
    with pytest.raises(DatasetMissingError):
        loader.load(tmp_path / "empty")


def test_harness_dry_run_plain_files_no_api(tmp_path: Path) -> None:
    backend = PlainFilesBackend(tmp_path / "store")
    provider = AnthropicProvider(dry_run=True)
    payload = run_benchmark("locomo", FIXTURES / "locomo", backend, provider, dry_run=True)

    assert payload["benchmark"] == "locomo"
    assert payload["backend"] == "plain_files"
    assert payload["task_count"] > 0
    # dry-run makes no official-metric claim
    assert payload["official_metric_scores"] is None
    assert "DRY RUN" in payload["label"]
    # synthetic fixture answers should be retrievable by the naive baseline
    assert payload["retrieval_hit_proxy_mean"] > 0
    # zero real spend, everything estimated
    assert payload["provenance"]["cost"]["estimated"] is True

    out = write_results(tmp_path / "results" / "r.json", payload)
    assert json.loads(out.read_text())["benchmark"] == "locomo"


def test_results_provenance_schema(tmp_path: Path) -> None:
    backend = SqliteFtsBackend()
    provider = AnthropicProvider(dry_run=True)
    payload = run_benchmark("helmet", FIXTURES / "helmet", backend, provider, dry_run=True)
    provenance = payload["provenance"]

    for key in ["git_sha", "harness_version", "dataset", "model_id",
                "prompts_hash", "cost", "timestamp", "mode"]:
        assert key in provenance, f"missing provenance key {key}"
    dataset = provenance["dataset"]
    for key in ["name", "official_url", "pinned_version", "sha256_pinned", "sha256_actual"]:
        assert key in dataset, f"missing dataset provenance key {key}"
    assert dataset["sha256_actual"]  # bound to the actual local data file
    cost = provenance["cost"]
    for key in ["input_tokens", "output_tokens", "cost_usd", "estimated"]:
        assert key in cost, f"missing cost key {key}"
    assert cost["input_tokens"] > 0
    assert provenance["mode"] == "dry_run"
    assert len(provenance["prompts_hash"]) == 64


def test_live_mode_refused_in_phase_a() -> None:
    backend = PlainFilesBackend()
    provider = AnthropicProvider(dry_run=True)
    with pytest.raises(RuntimeError, match="Phase B"):
        run_benchmark("locomo", FIXTURES / "locomo", backend, provider, dry_run=False)


def test_anthropic_provider_dry_run_estimates_without_key(monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    provider = AnthropicProvider(dry_run=True)
    usage = provider.estimate("hello " * 100)
    assert usage.estimated is True
    assert usage.input_tokens > 0
    assert usage.cost_usd > 0
    completion = provider.complete("hello")
    assert completion.text == ""
    live = AnthropicProvider(dry_run=False)
    with pytest.raises(RuntimeError, match="Phase A"):
        live.complete("hello")


def test_sqlite_baseline_ingest_recall() -> None:
    backend = SqliteFtsBackend()
    backend.ingest("a", "SYNTHETIC: the launch code color is vermilion")
    backend.ingest("b", "SYNTHETIC: unrelated gardening notes about tulips")
    results = backend.recall("what color is the launch code", k=1)
    assert results and "vermilion" in results[0]
    backend.reset()
    assert backend.recall("vermilion") == []


def test_token_f1_metric() -> None:
    assert token_f1("the Riverside half marathon", ("the Riverside half marathon",)) == 1.0
    assert token_f1("nothing relevant", ("Biscuit",)) == 0.0
    assert 0.0 < token_f1("pale green paint", ("pale green",)) < 1.01


def test_unsupported_benchmarks_documented() -> None:
    text = (REPO / "benchmarks" / "external" / "UNSUPPORTED.md").read_text(encoding="utf-8")
    for name in ["BEAM-1M", "BEAM-10M", "MemoryAgentBench", "MemBench", "MEMPROBE",
                 "Memora/FAMA", "LongMemEval-V2", "MemoryArena", "Mem2ActBench",
                 "EvoMemBench", "PerMemBench", "MemEvoBench", "MPBench", "RGB", "AgentDAM"]:
        assert name in text, f"{name} missing from UNSUPPORTED.md"


def test_lineage_axes_skip_visibly_without_intake_csv(monkeypatch, tmp_path: Path) -> None:
    """Clean-clone honesty: lineage axes SKIP with a reason, never crash or pass."""
    from benchmarks import lineage_import_coverage

    monkeypatch.setenv("ZEREF_LINEAGE_INTAKE_CSV", str(tmp_path / "absent.csv"))
    result = lineage_import_coverage.run()
    assert result["skipped"] is True
    assert result["score"] is None
    assert "not found" in result["reason"]


def test_run_all_completes_on_clean_clone_env(monkeypatch, tmp_path: Path) -> None:
    """python3 benchmarks/run-all.py must complete without FileNotFoundError
    even when the lineage intake CSV is absent (clean clone)."""
    env = {"ZEREF_LINEAGE_INTAKE_CSV": str(tmp_path / "absent.csv")}
    completed = subprocess.run(
        [sys.executable, str(REPO / "benchmarks" / "run-all.py"),
         "--out-report", str(tmp_path / "report.md"),
         "--out-json", str(tmp_path / "results.json")],
        capture_output=True, text=True, cwd=str(REPO),
        env={**__import__("os").environ, **env},
    )
    assert "FileNotFoundError" not in completed.stderr
    assert "SKIPPED" in completed.stdout
    report = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert "Internal quality axes" in report
    assert "NOT external benchmark results" in report
    assert "SKIPPED" in report
    payload = json.loads((tmp_path / "results.json").read_text(encoding="utf-8"))
    assert "lineage_import_coverage" in payload["skipped_axes"]
