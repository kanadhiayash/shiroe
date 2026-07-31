"""
privacy-audit: allow-file "Tests reference env-var names, synthetic fixture text, and a sentinel string standing in for a key value; no real credentials or user data."

Wave 4 — external benchmark harness: ConvoMem loader, the three-arm runner
(zeref / full_context / bm25), the Gemini JudgeClient interface (tested only
via DeterministicFakeJudge), the pre-run cost estimator, and the
`zeref benchmark external` CLI.

No network, no API key, no dataset download: every test here runs against
the tiny synthetic fixtures already committed under benchmarks/external/
fixtures/, using DeterministicFakeJudge and AnthropicProvider(dry_run=True).
"""

from __future__ import annotations

import argparse
import json
import socket
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from benchmarks.external.baselines.bm25 import Bm25Backend
from benchmarks.external.baselines.full_context import FullContextBackend
from benchmarks.external.baselines.shiroe_backend import ShiroeBackend
from benchmarks.external.cost import (
    COST_CEILING_USD,
    DEFAULT_MAX_COST_USD,
    effective_max_cost,
    estimate_run_cost,
)
from benchmarks.external.judges.base import JudgeClient, Verdict
from benchmarks.external.judges.fake import DeterministicFakeJudge
from benchmarks.external.judges.gemini import GeminiJudgeClient, _read_api_key
from benchmarks.external.loaders import LOADERS, get_loader
from benchmarks.external.providers.anthropic import AnthropicProvider
from benchmarks.external.providers.base import Usage
from benchmarks.external.runner import ALL_ARMS, resolve_arms, run_three_arms
from benchmarks.external.schema import DatasetMissingError

FIXTURES = REPO / "benchmarks" / "external" / "fixtures"
LOCOMO_DIR = FIXTURES / "locomo"

SENTINEL_KEY = "SENTINEL-do-not-leak-AIzaSyFAKEFAKEFAKEFAKEFAKEFAKEFAKE12"


# --- ConvoMem loader ---------------------------------------------------------

def test_convomem_is_registered() -> None:
    assert "convomem" in LOADERS
    assert get_loader("convomem").NAME == "convomem"


def test_convomem_loader_parses_fixture() -> None:
    loader = get_loader("convomem")
    tasks = loader.load(FIXTURES / "convomem")
    assert tasks
    assert all(t.benchmark == "convomem" for t in tasks)
    assert all(t.sessions for t in tasks)


def test_convomem_missing_dataset_fails_clearly(tmp_path: Path) -> None:
    loader = get_loader("convomem")
    result = loader.check(tmp_path / "empty")
    assert not result.ok
    message = " ".join(result.errors)
    assert loader.OFFICIAL_URL in message
    assert "Manual download" in message
    with pytest.raises(DatasetMissingError):
        loader.load(tmp_path / "empty")


# --- Backends: ingest/recall/reset contract ----------------------------------

@pytest.mark.parametrize("backend_cls", [FullContextBackend, Bm25Backend, ShiroeBackend])
def test_backend_contract(backend_cls) -> None:
    backend = backend_cls()
    backend.reset()
    backend.ingest("a", "SYNTHETIC: the launch code color is vermilion")
    backend.ingest("b", "SYNTHETIC: unrelated gardening notes about tulips")
    retrieved = backend.recall("what color is the launch code", k=1)
    assert retrieved
    assert any("vermilion" in chunk for chunk in retrieved)
    backend.reset()
    assert backend.recall("vermilion") == []


def test_full_context_ignores_k() -> None:
    backend = FullContextBackend()
    for i in range(5):
        backend.ingest(str(i), f"SYNTHETIC chunk {i}")
    assert len(backend.recall("chunk", k=1)) == 5


def test_bm25_ranks_by_relevance() -> None:
    backend = Bm25Backend()
    backend.ingest("a", "SYNTHETIC: cats are wonderful pets")
    backend.ingest("b", "SYNTHETIC: gardening tulips in spring")
    top = backend.recall("cats pets", k=1)
    assert top and "cats" in top[0]


# --- Runner: three arms end-to-end -------------------------------------------

def test_runner_all_arms_registered() -> None:
    assert set(ALL_ARMS) == {"shiroe", "full_context", "bm25"}


def test_resolve_arms() -> None:
    assert resolve_arms(None) == ALL_ARMS
    assert resolve_arms("all") == ALL_ARMS
    assert resolve_arms("shiroe,bm25") == ("shiroe", "bm25")
    with pytest.raises(KeyError):
        resolve_arms("not-a-real-arm")
    with pytest.raises(ValueError):
        resolve_arms("")


def test_proxy_mode_runs_all_arms_zero_calls(monkeypatch) -> None:
    """Dry-run makes zero network calls — proved by breaking the transport."""
    def _no_network(*args, **kwargs):
        raise AssertionError("socket.connect was called — dry-run must never touch the network")

    monkeypatch.setattr(socket.socket, "connect", _no_network)
    monkeypatch.setattr(socket.socket, "connect_ex", _no_network)

    payload = run_three_arms("locomo", LOCOMO_DIR, scored=False)
    assert payload["mode"] == "proxy"
    assert set(payload["results_by_arm"]) == {"shiroe", "full_context", "bm25"}
    assert payload["task_count"] > 0
    for arm, result in payload["results_by_arm"].items():
        assert result["task_count"] == payload["task_count"]
        assert result["retrieval_hit_proxy_mean"] is not None
        assert result["official_metric_mean"] is None  # no provider called
    assert payload["provenance"]["cost"]["cost_usd"] == 0.0
    assert payload["aborted"] is False


def test_scored_mode_drives_three_arms_with_fake_judge() -> None:
    provider = AnthropicProvider(dry_run=True)
    judge = DeterministicFakeJudge()
    payload = run_three_arms(
        "locomo", LOCOMO_DIR, scored=True, provider=provider, judge=judge, max_cost=500,
    )
    assert payload["mode"] == "scored"
    assert set(payload["results_by_arm"]) == {"shiroe", "full_context", "bm25"}
    assert payload["aborted"] is False
    for arm, result in payload["results_by_arm"].items():
        for record in result["tasks"]:
            assert record["prediction"] is not None
            assert record["official_score"] is not None
            assert record["judge_correct"] is not None
    assert payload["provenance"]["judge_model"] == "deterministic-fake-judge-v1"
    assert payload["provenance"]["model_id"] == "claude-sonnet-4-5"


def test_scored_requires_provider_and_judge() -> None:
    with pytest.raises(ValueError):
        run_three_arms("locomo", LOCOMO_DIR, scored=True)


def test_runner_limit_is_seeded_and_deterministic() -> None:
    provider = AnthropicProvider(dry_run=True)
    judge = DeterministicFakeJudge()
    p1 = run_three_arms("locomo", LOCOMO_DIR, scored=True, provider=provider, judge=judge,
                        max_cost=500, seed=7, limit=2, arms="shiroe")
    p2 = run_three_arms("locomo", LOCOMO_DIR, scored=True, provider=provider, judge=judge,
                        max_cost=500, seed=7, limit=2, arms="shiroe")
    ids1 = [t["task_id"] for t in p1["results_by_arm"]["shiroe"]["tasks"]]
    ids2 = [t["task_id"] for t in p2["results_by_arm"]["shiroe"]["tasks"]]
    assert ids1 == ids2
    assert len(ids1) == 2


# --- Cost estimator -----------------------------------------------------------

def test_cost_estimate_math_matches_manual_sum() -> None:
    provider = AnthropicProvider(dry_run=True)
    judge = DeterministicFakeJudge()
    tasks = get_loader("locomo").load(LOCOMO_DIR)
    arms = ("shiroe", "full_context", "bm25")

    estimate = estimate_run_cost("locomo", LOCOMO_DIR, arms, provider, judge)

    assert estimate.task_count == len(tasks)
    assert estimate.judge_call_count == len(tasks) * len(arms)
    assert estimate.provider_call_count == len(tasks) * len(arms)

    expected_provider = sum(provider.estimate(t.question).cost_usd for t in tasks) * len(arms)
    expected_judge = sum(judge.estimate(t.question, t.answers, "").cost_usd for t in tasks) * len(arms)
    assert estimate.est_provider_cost_usd == pytest.approx(expected_provider)
    assert estimate.est_judge_cost_usd == pytest.approx(expected_judge)
    assert estimate.est_total_cost_usd == pytest.approx(expected_provider + expected_judge)


def test_effective_max_cost_default_and_clamp() -> None:
    value, clamped = effective_max_cost(None)
    assert value == DEFAULT_MAX_COST_USD
    assert clamped is False

    value, clamped = effective_max_cost(50.0)
    assert value == 50.0
    assert clamped is False

    value, clamped = effective_max_cost(COST_CEILING_USD + 1000)
    assert value == COST_CEILING_USD
    assert clamped is True


def test_exceeding_max_cost_aborts_mid_run() -> None:
    provider = AnthropicProvider(dry_run=True)
    judge = DeterministicFakeJudge()
    payload = run_three_arms(
        "locomo", LOCOMO_DIR, scored=True, provider=provider, judge=judge,
        max_cost=0.00000001,
    )
    assert payload["aborted"] is True
    assert payload["provenance"]["exclusions"]
    assert all(e["reason"] == "cost_ceiling_reached" for e in payload["provenance"]["exclusions"])
    # nothing that was excluded ever got a prediction
    for result in payload["results_by_arm"].values():
        excluded_ids = {e["task_id"] for e in payload["provenance"]["exclusions"] if e["arm"] == result["backend"]}
        for record in result["tasks"]:
            if record["task_id"] in excluded_ids:
                assert record["prediction"] is None


def test_generous_max_cost_never_aborts() -> None:
    provider = AnthropicProvider(dry_run=True)
    judge = DeterministicFakeJudge()
    payload = run_three_arms(
        "locomo", LOCOMO_DIR, scored=True, provider=provider, judge=judge, max_cost=COST_CEILING_USD,
    )
    assert payload["aborted"] is False
    assert payload["provenance"]["exclusions"] == []


# --- Provenance: complete + reproducible --------------------------------------

def _strip_timestamp(payload: dict) -> dict:
    payload = json.loads(json.dumps(payload))
    payload["provenance"].pop("timestamp", None)
    return payload


def test_provenance_has_wave4_fields() -> None:
    provider = AnthropicProvider(dry_run=True)
    judge = DeterministicFakeJudge()
    payload = run_three_arms(
        "locomo", LOCOMO_DIR, scored=True, provider=provider, judge=judge,
        max_cost=500, seed=3,
    )
    provenance = payload["provenance"]
    for key in ["git_sha", "harness_version", "dataset", "model_id", "judge_model",
                "seed", "prompts_hash", "cost", "avg_latency_ms", "failures",
                "exclusions", "timestamp", "mode"]:
        assert key in provenance, f"missing provenance key {key}"
    assert provenance["seed"] == 3
    assert provenance["judge_model"] == "deterministic-fake-judge-v1"
    assert provenance["avg_latency_ms"] == 0.0
    assert provenance["failures"] == []


def test_provenance_reproducible_modulo_timestamp() -> None:
    provider = AnthropicProvider(dry_run=True)
    judge = DeterministicFakeJudge()
    kwargs = dict(scored=True, provider=provider, judge=judge, max_cost=500, seed=1)
    p1 = run_three_arms("locomo", LOCOMO_DIR, **kwargs)
    p2 = run_three_arms("locomo", LOCOMO_DIR, **kwargs)
    assert _strip_timestamp(p1) == _strip_timestamp(p2)


def test_proxy_provenance_reproducible_modulo_timestamp() -> None:
    p1 = run_three_arms("locomo", LOCOMO_DIR, scored=False)
    p2 = run_three_arms("locomo", LOCOMO_DIR, scored=False)
    assert _strip_timestamp(p1) == _strip_timestamp(p2)


# --- Judge interface: swappable, fake-only in tests ---------------------------

def test_judgeclient_is_abstract() -> None:
    with pytest.raises(TypeError):
        JudgeClient()  # type: ignore[abstract]


def test_deterministic_fake_judge_correctness() -> None:
    judge = DeterministicFakeJudge()
    correct = judge.judge("q", ("Paris",), "Paris")
    wrong = judge.judge("q", ("Paris",), "London")
    assert correct.correct is True and correct.score == 1.0
    assert wrong.correct is False and wrong.score == 0.0
    assert isinstance(correct.usage, Usage)
    assert correct.usage.cost_usd > 0  # nonzero synthetic cost exercises accounting math


def test_gemini_judge_never_invoked_live_in_tests(monkeypatch) -> None:
    """The real client is swappable but this test — like every other test in
    this repo — only ever calls estimate(), never judge()."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    judge = GeminiJudgeClient()
    assert judge.has_key() is False
    usage = judge.estimate("question", ("answer",), "prediction")
    assert usage.estimated is True
    assert usage.input_tokens > 0
    with pytest.raises(RuntimeError, match="disabled"):
        judge.judge("question", ("answer",), "prediction")


def test_gemini_judge_reads_env_local(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    # key reading lives in the shared transport now (gemini_api), so the
    # judge and provider cannot drift apart on it
    monkeypatch.setattr("benchmarks.external.gemini_api.REPO", tmp_path)
    (tmp_path / ".env.local").write_text(f'GEMINI_API_KEY="{SENTINEL_KEY}"\n', encoding="utf-8")
    judge = GeminiJudgeClient()
    assert judge.has_key() is True
    # the raw value must never be retained as a readable attribute
    assert SENTINEL_KEY not in vars(judge).values()
    for value in vars(judge).values():
        assert SENTINEL_KEY not in str(value)


# --- API key never emitted, on any code path ----------------------------------

def test_api_key_never_emitted(monkeypatch, capsys) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", SENTINEL_KEY)

    # 1) reading it directly returns it (sanity: the sentinel plumbing works)...
    assert _read_api_key() == SENTINEL_KEY

    # 2) ...but the client never stores or exposes the raw value.
    judge = GeminiJudgeClient()
    assert SENTINEL_KEY not in repr(vars(judge))
    assert SENTINEL_KEY not in str(vars(judge))

    # 3) estimate() output never contains it.
    usage = judge.estimate("q", ("a",), "p")
    assert SENTINEL_KEY not in json.dumps(usage.to_dict())

    # 4) judge() raises — the exception message must not contain it.
    with pytest.raises(RuntimeError) as excinfo:
        judge.judge("q", ("a",), "p")
    assert SENTINEL_KEY not in str(excinfo.value)

    # 5) a full scored runner pass (judge failures included) never leaks it.
    provider = AnthropicProvider(dry_run=True)
    payload = run_three_arms(
        "locomo", LOCOMO_DIR, scored=True, provider=provider, judge=judge, max_cost=500,
    )
    dumped = json.dumps(payload)
    assert SENTINEL_KEY not in dumped
    assert payload["provenance"]["failures"]  # every call failed cleanly (judge() raises)
    for failure in payload["provenance"]["failures"]:
        assert SENTINEL_KEY not in failure["error"]

    # 6) nothing printed to stdout/stderr along the way carries it either.
    captured = capsys.readouterr()
    assert SENTINEL_KEY not in captured.out
    assert SENTINEL_KEY not in captured.err


def test_api_key_never_emitted_via_cli(monkeypatch, capsys, tmp_path: Path) -> None:
    from shiroe import cli_benchmark

    monkeypatch.setenv("GEMINI_API_KEY", SENTINEL_KEY)
    out_path = tmp_path / "results.json"
    args = argparse.Namespace(
        benchmark_command="external", benchmark="locomo", data=str(LOCOMO_DIR),
        arms="shiroe", dry_run=False, live=True, confirm=True, max_cost=500.0,
        provider="anthropic", judge="gemini", seed=0, limit=None,
        out=str(out_path), format="text",
    )
    exit_code = cli_benchmark.handle(args)
    assert exit_code == 0

    captured = capsys.readouterr()
    assert SENTINEL_KEY not in captured.out
    assert SENTINEL_KEY not in captured.err
    assert SENTINEL_KEY not in out_path.read_text(encoding="utf-8")


# --- CLI ------------------------------------------------------------------

def test_cli_registers_benchmark_command() -> None:
    from shiroe.cli import _build_parser

    parser = _build_parser()
    args = parser.parse_args([
        "benchmark", "external", "--benchmark", "locomo", "--data", str(LOCOMO_DIR),
    ])
    assert args.command == "benchmark"
    assert args.benchmark_command == "external"
    assert args.dry_run is False  # store_true default; proxy mode is the absence of --live
    assert args.live is False


def test_cli_default_is_proxy_mode_and_json_stdout_is_clean(capsys) -> None:
    """--format json must print ONLY the payload to stdout — cost-estimate
    and other diagnostics go to stderr so stdout stays pipeable."""
    from shiroe import cli_benchmark

    args = argparse.Namespace(
        benchmark_command="external", benchmark="locomo", data=str(LOCOMO_DIR),
        arms="all", dry_run=False, live=False, confirm=False, max_cost=None,
        provider="anthropic", judge="fake", seed=0, limit=None, out=None, format="json",
    )
    exit_code = cli_benchmark.handle(args)
    assert exit_code == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)  # raises if stdout has anything but the JSON payload
    assert payload["mode"] == "proxy"
    assert "cost estimate" in captured.err


def test_cli_missing_dataset_fails_clearly(capsys) -> None:
    from shiroe import cli_benchmark

    args = argparse.Namespace(
        benchmark_command="external", benchmark="locomo", data="/nonexistent/zeref-bench-path",
        arms="all", dry_run=False, live=False, confirm=False, max_cost=None,
        provider="anthropic", judge="fake", seed=0, limit=None, out=None, format="text",
    )
    exit_code = cli_benchmark.handle(args)
    assert exit_code == 1
    captured = capsys.readouterr()
    assert "Manual download" in captured.err


def test_cli_live_without_confirm_refuses(capsys) -> None:
    from shiroe import cli_benchmark

    args = argparse.Namespace(
        benchmark_command="external", benchmark="locomo", data=str(LOCOMO_DIR),
        arms="all", dry_run=False, live=True, confirm=False, max_cost=None,
        provider="anthropic", judge="fake", seed=0, limit=None, out=None, format="text",
    )
    exit_code = cli_benchmark.handle(args)
    assert exit_code == 1
    assert "--confirm" in capsys.readouterr().err


def test_cli_live_over_budget_refuses(capsys) -> None:
    from shiroe import cli_benchmark

    args = argparse.Namespace(
        benchmark_command="external", benchmark="locomo", data=str(LOCOMO_DIR),
        arms="all", dry_run=False, live=True, confirm=True, max_cost=0.00000001,
        provider="anthropic", judge="fake", seed=0, limit=None, out=None, format="text",
    )
    exit_code = cli_benchmark.handle(args)
    assert exit_code == 1
    assert "refusing" in capsys.readouterr().err


def test_cli_dry_run_flag_wins_over_live(capsys) -> None:
    """Passing both --live and --dry-run must stay in (zero-network) proxy mode."""
    from shiroe import cli_benchmark

    args = argparse.Namespace(
        benchmark_command="external", benchmark="locomo", data=str(LOCOMO_DIR),
        arms="all", dry_run=True, live=True, confirm=True, max_cost=500.0,
        provider="anthropic", judge="fake", seed=0, limit=None, out=None, format="text",
    )
    exit_code = cli_benchmark.handle(args)
    assert exit_code == 0
    assert "PROXY RUN" in capsys.readouterr().out


def test_cli_live_confirmed_scored_run_with_fake_judge(capsys, tmp_path: Path) -> None:
    from shiroe import cli_benchmark

    out_path = tmp_path / "out.json"
    args = argparse.Namespace(
        benchmark_command="external", benchmark="locomo", data=str(LOCOMO_DIR),
        arms="all", dry_run=False, live=True, confirm=True, max_cost=500.0,
        provider="anthropic", judge="fake", seed=0, limit=None,
        out=str(out_path), format="text",
    )
    exit_code = cli_benchmark.handle(args)
    assert exit_code == 0
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["mode"] == "scored"
    assert payload["aborted"] is False


def test_cli_unknown_benchmark(capsys) -> None:
    from shiroe import cli_benchmark

    args = argparse.Namespace(
        benchmark_command="external", benchmark="not-a-benchmark", data=str(LOCOMO_DIR),
        arms="all", dry_run=False, live=False, confirm=False, max_cost=None,
        provider="anthropic", judge="fake", seed=0, limit=None, out=None, format="text",
    )
    exit_code = cli_benchmark.handle(args)
    assert exit_code == 1
    assert "unknown benchmark" in capsys.readouterr().err


def test_cli_help_does_not_crash() -> None:
    """Smoke test the real argparse wiring end-to-end via subprocess."""
    import subprocess

    completed = subprocess.run(
        [sys.executable, "-m", "shiroe.cli", "benchmark", "external", "--help"],
        capture_output=True, text=True, cwd=str(REPO),
    )
    assert completed.returncode == 0
    assert "--max-cost" in completed.stdout
    assert "--confirm" in completed.stdout


def test_chunking_splits_single_session_haystacks() -> None:
    """A one-session task must still yield many chunks.

    ConvoMem, PersonaMem, RULER and HELMET loaders all emit a single session.
    When chunking followed session boundaries, that produced exactly one
    chunk, `recall(k)` returned the entire haystack, and all three arms
    received a byte-identical prompt — three identical scores presented as a
    three-way tie. This asserts the property that broke.
    """
    from benchmarks.external.harness import CHUNK_TARGET_CHARS, iter_chunks
    from benchmarks.external.schema import Task, Turn

    long_turn = "word " * 40_000  # ~200k chars in ONE turn, as RULER ships it
    task = Task(
        task_id="t", benchmark="synthetic", question="q", answers=("a",),
        sessions=((Turn(role="context", content=long_turn),),), metric="token_f1",
    )
    chunks = list(iter_chunks(task))
    assert len(chunks) > 20, f"single-turn haystack produced {len(chunks)} chunk(s)"
    assert all(len(text) <= CHUNK_TARGET_CHARS for _, text in chunks)
    assert len({cid for cid, _ in chunks}) == len(chunks), "chunk ids must be unique"
    # Order preserved, so the full_context arm can reconstruct the haystack.
    assert "".join(t.split(": ", 1)[-1] for _, t in chunks[:1])


def test_arms_diverge_on_a_multi_chunk_task() -> None:
    """zeref / full_context / bm25 must not all receive the same context."""
    from benchmarks.external.harness import build_prompt, ingest_task
    from benchmarks.external.runner import ARM_BACKENDS
    from benchmarks.external.schema import Task, Turn

    sessions = tuple(
        (Turn(role="user", content=f"Session {i} discusses topic-{i} " + "filler " * 900),)
        for i in range(12)
    )
    task = Task(
        task_id="t", benchmark="synthetic", question="what does topic-7 discuss?",
        answers=("topic-7",), sessions=sessions, metric="token_f1",
    )
    prompts = {}
    for arm, backend_cls in ARM_BACKENDS.items():
        backend = backend_cls()
        ingest_task(backend, task)
        prompts[arm] = build_prompt(task, backend.recall(task.question, k=5))
    assert len(set(prompts.values())) > 1, "all arms received identical context"
    assert len(prompts["full_context"]) > len(prompts["bm25"]), (
        "full_context must carry more context than a top-k retriever"
    )


def test_degenerate_tasks_are_flagged_not_silently_tied() -> None:
    """A haystack smaller than one chunk cannot discriminate between arms.

    Such a task hands every arm the same context, so all arms necessarily
    score identically. Counting that as a three-way tie drags every arm's
    mean toward the others; ~37% of ConvoMem is this shape. The run must say
    so rather than report a tie.
    """
    from benchmarks.external.runner import run_three_arms

    payload = run_three_arms("locomo", LOCOMO_DIR, arms="all", scored=False, limit=None)
    assert "degenerate_task_count" in payload
    assert "degenerate_task_ids" in payload
    assert payload["chunk_target_chars"] > 0
    for arm_result in payload["results_by_arm"].values():
        assert "discriminating_task_count" in arm_result
        assert arm_result["discriminating_task_count"] <= arm_result["task_count"]
        for record in arm_result["tasks"]:
            assert "identical_context_across_arms" in record
            assert "context_digest" in record


def test_proxy_and_scored_modes_are_labelled_correctly() -> None:
    """Guards the boolean `scored` parameter against being shadowed.

    A list comprehension named `scored` inside this function once rebound the
    parameter; an empty list is falsy, so a genuine scored run reported
    mode="proxy" and stamped its provenance `estimated`.
    """
    from benchmarks.external.judges.fake import DeterministicFakeJudge
    from benchmarks.external.providers.anthropic import AnthropicProvider
    from benchmarks.external.runner import run_three_arms

    proxy = run_three_arms("locomo", LOCOMO_DIR, arms="all", scored=False)
    assert proxy["mode"] == "proxy" and "PROXY RUN" in proxy["label"]

    scored = run_three_arms(
        "locomo", LOCOMO_DIR, arms="all", scored=True,
        provider=AnthropicProvider(dry_run=True), judge=DeterministicFakeJudge(),
        max_cost=500.0,
    )
    assert scored["mode"] == "scored", "scored run mislabelled as proxy"
    assert scored["provenance"]["mode"] == "scored"
