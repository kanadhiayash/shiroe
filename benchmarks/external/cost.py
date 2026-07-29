"""
privacy-audit: allow-file "Cost estimator names dollar-figure fields and dataset task counts as spec; no user data."

Pre-run cost estimation and budget-ceiling enforcement for scored runs.

Every function here is pure arithmetic over a local dataset's task count and
a provider/judge's own estimate() methods (also network-free) — nothing in
this module makes a network call. `run_three_arms` (runner.py) uses
`effective_max_cost` to clamp any requested budget before a scored run, and
checks the running total against it before every provider/judge call.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from benchmarks.external.judges.base import JudgeClient
from benchmarks.external.loaders import get_loader
from benchmarks.external.providers.base import Provider

# Hard ceiling: no CLI flag or code path may authorize a projected spend
# above this, regardless of what --max-cost requests. Bump only with an
# explicit human-reviewed change, never silently.
COST_CEILING_USD = 500.0

# Conservative default when the caller doesn't pass --max-cost at all —
# small enough that an accidental full-dataset live run can't run away.
DEFAULT_MAX_COST_USD = 5.0


@dataclass(frozen=True)
class CostEstimate:
    benchmark: str
    task_count: int
    arms: tuple[str, ...]
    judge_call_count: int
    provider_call_count: int
    est_provider_cost_usd: float
    est_judge_cost_usd: float
    est_total_cost_usd: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "benchmark": self.benchmark,
            "task_count": self.task_count,
            "arms": list(self.arms),
            "judge_call_count": self.judge_call_count,
            "provider_call_count": self.provider_call_count,
            "est_provider_cost_usd": round(self.est_provider_cost_usd, 6),
            "est_judge_cost_usd": round(self.est_judge_cost_usd, 6),
            "est_total_cost_usd": round(self.est_total_cost_usd, 6),
        }


def estimate_run_cost(
    benchmark: str,
    data_dir: str | Path,
    arms: tuple[str, ...],
    provider: Provider,
    judge: JudgeClient,
    limit: int | None = None,
    seed: int = 0,
) -> CostEstimate:
    """Estimate judge-call count and dollar cost for a scored run, BEFORE
    running anything. Reads the local dataset file (no network) to get an
    exact task count and per-task question text for a representative
    per-call cost; the real per-arm prompt also carries retrieved context,
    which is unknowable before ingest/recall runs, so this is a lower-bound
    estimate — real cost is reported afterward via provenance, not
    predicted exactly here.
    """
    loader = get_loader(benchmark)
    tasks = loader.load(Path(data_dir))
    # Must apply the SAME sampling the runner will, or a --limit run is priced
    # for the whole dataset and the budget gate refuses a run that would in
    # fact have cost a fraction of the ceiling. Mirrors run_three_arms().
    if limit is not None and limit < len(tasks):
        tasks = random.Random(seed).sample(tasks, limit)
    task_count = len(tasks)
    calls_per_arm = task_count
    total_calls = calls_per_arm * len(arms)

    provider_cost = 0.0
    judge_cost = 0.0
    for task in tasks:
        provider_cost += provider.estimate(task.question).cost_usd * len(arms)
        judge_cost += judge.estimate(task.question, task.answers, "").cost_usd * len(arms)

    return CostEstimate(
        benchmark=benchmark,
        task_count=task_count,
        arms=tuple(arms),
        judge_call_count=total_calls,
        provider_call_count=total_calls,
        est_provider_cost_usd=provider_cost,
        est_judge_cost_usd=judge_cost,
        est_total_cost_usd=provider_cost + judge_cost,
    )


def effective_max_cost(max_cost: float | None) -> tuple[float, bool]:
    """Clamp a requested budget to the hard ceiling.

    Returns (effective_value, was_clamped). None -> the conservative
    default, never the ceiling itself, so "forgot to pass --max-cost" fails
    safe to a small budget instead of the full $500.
    """
    requested = DEFAULT_MAX_COST_USD if max_cost is None else max_cost
    if requested > COST_CEILING_USD:
        return COST_CEILING_USD, True
    return requested, False
