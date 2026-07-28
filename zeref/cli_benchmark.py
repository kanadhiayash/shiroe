"""CLI subcommands for ``zeref benchmark``.

Split from ``zeref.cli`` to keep that module from ballooning further, same
pattern as ``zeref.cli_capability`` / ``zeref.cli_providers``. Registered via
``register(sub)`` and ``handle(args)``.

``benchmarks/external`` is dev/test-only (never packaged under ``zeref*`` —
see the ``benchmark`` extra in pyproject.toml), so the import is lazy and
fails with a clear message outside a source checkout.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def register(sub) -> None:
    p = sub.add_parser(
        "benchmark",
        help="External benchmark harness (dataset loaders, 3-arm runner, judge, cost gate)",
    )
    bsub = p.add_subparsers(dest="benchmark_command", required=True)

    ext = bsub.add_parser(
        "external",
        help="Run LoCoMo/LongMemEval/ConvoMem/... across the zeref, full_context, and bm25 arms",
    )
    ext.add_argument("--benchmark", required=True,
                     help="locomo | longmemeval | convomem | personamem | ruler | helmet")
    ext.add_argument("--data", required=True,
                     help="local dataset directory (manual download only; no auto-downloads)")
    ext.add_argument("--arms", default="all",
                     help="comma-separated arm names, or 'all' (zeref,full_context,bm25)")
    ext.add_argument("--dry-run", action="store_true",
                     help="force proxy mode: ingest+recall only, zero network calls "
                          "(this is the default whenever --live is absent; passing both "
                          "--live and --dry-run keeps proxy mode, safety wins)")
    ext.add_argument("--live", action="store_true",
                     help="opt into a scored run (provider+judge calls); requires --confirm "
                          "and a cost estimate under the effective --max-cost")
    ext.add_argument("--confirm", action="store_true",
                     help="required together with --live to proceed past the cost estimate")
    ext.add_argument("--max-cost", type=float, default=None,
                     help="USD budget ceiling for a --live run (default: conservative; "
                          "hard ceiling: $500, see benchmarks.external.cost.COST_CEILING_USD)")
    ext.add_argument("--provider", default="anthropic", choices=["anthropic"])
    ext.add_argument("--judge", default="gemini", choices=["fake", "gemini"])
    ext.add_argument("--seed", type=int, default=0)
    ext.add_argument("--limit", type=int, default=None,
                     help="randomly sample at most N tasks (seeded by --seed)")
    ext.add_argument("--out", default=None, help="write results JSON here instead of stdout")
    ext.add_argument("--format", choices=["text", "json"], default="text")


def _load_harness_modules():
    """Lazy import of the dev/test-only external benchmark harness."""
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from benchmarks.external.cost import COST_CEILING_USD, effective_max_cost, estimate_run_cost
    from benchmarks.external.judges.fake import DeterministicFakeJudge
    from benchmarks.external.judges.gemini import GeminiJudgeClient
    from benchmarks.external.providers.anthropic import AnthropicProvider
    from benchmarks.external.runner import resolve_arms, run_three_arms, write_results
    from benchmarks.external.schema import DatasetMissingError

    return {
        "COST_CEILING_USD": COST_CEILING_USD,
        "effective_max_cost": effective_max_cost,
        "estimate_run_cost": estimate_run_cost,
        "DeterministicFakeJudge": DeterministicFakeJudge,
        "GeminiJudgeClient": GeminiJudgeClient,
        "AnthropicProvider": AnthropicProvider,
        "resolve_arms": resolve_arms,
        "run_three_arms": run_three_arms,
        "write_results": write_results,
        "DatasetMissingError": DatasetMissingError,
    }


def handle(args: argparse.Namespace) -> int:
    if args.benchmark_command == "external":
        return _cmd_external(args)
    print("✘ unknown benchmark command")
    return 1


def _info(msg: str) -> None:
    """Diagnostic/progress line — stderr, so --format json stdout stays clean."""
    print(msg, file=sys.stderr)


def _error(msg: str) -> None:
    print(f"✘ {msg}", file=sys.stderr)


def _cmd_external(args: argparse.Namespace) -> int:
    try:
        m = _load_harness_modules()
    except ModuleNotFoundError as exc:
        _error(
            f"benchmarks/external is dev-only and not importable here ({exc}). "
            "Run this command from a source checkout of zeref-memory-engine, "
            "not from an installed zeref-os package."
        )
        return 1

    try:
        arm_names = m["resolve_arms"](args.arms)
    except (KeyError, ValueError) as exc:
        _error(str(exc))
        return 1

    provider = m["AnthropicProvider"](dry_run=True)
    judge = m["DeterministicFakeJudge"]() if args.judge == "fake" else m["GeminiJudgeClient"]()

    try:
        estimate = m["estimate_run_cost"](args.benchmark, args.data, arm_names, provider, judge)
    except (m["DatasetMissingError"], KeyError) as exc:
        _error(str(exc))
        return 1

    effective_cost, clamped = m["effective_max_cost"](args.max_cost)
    _info(
        f"cost estimate: {estimate.task_count} tasks x {len(arm_names)} arms = "
        f"{estimate.judge_call_count} judge calls, est. ${estimate.est_total_cost_usd:.4f} "
        f"(provider ${estimate.est_provider_cost_usd:.4f} + judge ${estimate.est_judge_cost_usd:.4f})"
    )
    if clamped:
        _info(f"  --max-cost {args.max_cost} exceeds the ${m['COST_CEILING_USD']:.2f} hard "
              f"ceiling; using ${m['COST_CEILING_USD']:.2f}.")
    _info(f"  budget: ${effective_cost:.4f}"
          + (" (default — pass --max-cost to raise, capped at the hard ceiling)"
             if args.max_cost is None else ""))

    scored = bool(args.live) and not args.dry_run

    if scored:
        if estimate.est_total_cost_usd > effective_cost:
            _error(
                f"refusing: estimated ${estimate.est_total_cost_usd:.4f} exceeds budget "
                f"${effective_cost:.4f}. Narrow --arms/--limit or raise --max-cost "
                f"(capped at the ${m['COST_CEILING_USD']:.2f} hard ceiling)."
            )
            return 1
        if not args.confirm:
            _error("pass --confirm to proceed with a --live run at the estimate above.")
            return 1

    try:
        if scored:
            payload = m["run_three_arms"](
                args.benchmark, args.data, arms=arm_names, scored=True,
                provider=provider, judge=judge, max_cost=effective_cost,
                seed=args.seed, limit=args.limit,
            )
        else:
            payload = m["run_three_arms"](
                args.benchmark, args.data, arms=arm_names, scored=False,
                seed=args.seed, limit=args.limit,
            )
    except m["DatasetMissingError"] as exc:
        _error(str(exc))
        return 1

    if payload["aborted"]:
        _info("⚠ run aborted mid-flight: projected cost reached --max-cost; "
              "see provenance.exclusions for what was skipped")

    if args.out:
        out = m["write_results"](args.out, payload)
        _info(f"results written to {out}")
    elif args.format == "json":
        print(json.dumps(payload, indent=2))
    else:
        print(payload["label"])
        print(f"benchmark={payload['benchmark']} arms={payload['arms']} "
              f"mode={payload['mode']} tasks={payload['task_count']}")
        for arm, res in payload["results_by_arm"].items():
            print(
                f"  {arm}: retrieval_hit_proxy_mean={res['retrieval_hit_proxy_mean']} "
                f"official_metric_mean={res['official_metric_mean']} "
                f"judge_accuracy={res['judge_accuracy']}"
            )
    return 0
