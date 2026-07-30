"""
privacy-audit: allow-file "Runner names provenance/cost schema fields as spec; no user data."

Three-arm external benchmark runner (Wave 4).

A Zeref retrieval number alone is meaningless, so every run evaluates three
arms side by side:

    (a) zeref        — the real zeref.memory search stack
    (b) full_context — no memory system at all (the honest floor; published
                        research shows full-context frequently beats
                        purpose-built memory products at small-to-medium
                        context lengths)
    (c) bm25          — a plain Okapi BM25 lexical ranker

Two modes:

- proxy (default, `scored=False`): ingest + recall per arm only, same
  `retrieval_hit_proxy` infrastructure signal as `harness.run_benchmark`.
  Never calls a provider or judge — zero network calls, full stop.
- scored (`scored=True`, requires a provider AND a judge): also generates a
  completion per task and judges it, checking the running cost against
  `max_cost` before every single provider/judge call and aborting the
  moment the next call would exceed it. Tests exercise this path with
  `AnthropicProvider(dry_run=True)` and `DeterministicFakeJudge` only —
  never a live client.
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import Any

from benchmarks.external.baselines.bm25 import Bm25Backend
from benchmarks.external.baselines.full_context import FullContextBackend
from benchmarks.external.baselines.zeref_backend import ZerefBackend
from benchmarks.external.cost import CostEstimate, effective_max_cost, estimate_run_cost
from benchmarks.external.harness import (
    CHUNK_TARGET_CHARS,
    METRICS,
    PROMPT_TEMPLATE,
    build_prompt,
    build_provenance,
    ingest_task,
    retrieval_hit,
    sha256_text,
)
from benchmarks.external.judges.base import JudgeClient
from benchmarks.external.loaders import get_loader
from benchmarks.external.providers.base import Provider

ARM_BACKENDS = {
    "zeref": ZerefBackend,
    "full_context": FullContextBackend,
    "bm25": Bm25Backend,
}
ALL_ARMS = tuple(ARM_BACKENDS)  # dict preserves insertion order: zeref, full_context, bm25


def resolve_arms(arms: str | list[str] | tuple[str, ...] | None) -> tuple[str, ...]:
    if arms is None or arms == "all":
        return ALL_ARMS
    names = [a.strip() for a in arms.split(",") if a.strip()] if isinstance(arms, str) else list(arms)
    unknown = sorted(set(names) - set(ARM_BACKENDS))
    if unknown:
        raise KeyError(f"unknown arm(s) {unknown}; supported: {sorted(ARM_BACKENDS)}")
    if not names:
        raise ValueError("arms must not be empty")
    return tuple(names)


def run_three_arms(
    benchmark: str,
    data_dir: str | Path,
    *,
    arms: str | list[str] | None = "all",
    provider: Provider | None = None,
    judge: JudgeClient | None = None,
    scored: bool = False,
    max_cost: float | None = None,
    seed: int = 0,
    limit: int | None = None,
    recall_k: int = 5,
) -> dict[str, Any]:
    """Run one benchmark across the given arms. `scored=False` (default)
    makes zero network-capable calls. `scored=True` requires both a
    provider and a judge, and enforces `max_cost` (clamped to the $500
    hard ceiling — see `cost.COST_CEILING_USD`) before every call.
    """
    if scored and (provider is None or judge is None):
        raise ValueError("scored=True requires both provider and judge")

    arm_names = resolve_arms(arms)
    loader = get_loader(benchmark)
    data_path = Path(data_dir)
    tasks = loader.load(data_path)
    if limit is not None and limit < len(tasks):
        tasks = random.Random(seed).sample(tasks, limit)
        tasks.sort(key=lambda t: t.task_id)  # deterministic output order post-sample

    effective_cost, clamped = (None, False)
    cost_estimate: CostEstimate | None = None
    if scored:
        effective_cost, clamped = effective_max_cost(max_cost)
        cost_estimate = estimate_run_cost(
            benchmark, data_path, arm_names, provider, judge, limit=limit, seed=seed
        )

    running_cost = 0.0
    # Snapshot so usage can be reported as a per-run delta (see usage_total).
    tokens_in_at_start = getattr(provider, "total_input_tokens", 0) if provider else 0
    tokens_out_at_start = getattr(provider, "total_output_tokens", 0) if provider else 0
    latencies: list[float] = []
    failures: list[dict[str, Any]] = []
    exclusions: list[dict[str, Any]] = []
    results_by_arm: dict[str, dict[str, Any]] = {}
    all_prompts: list[str] = []
    aborted = False

    for arm in arm_names:
        backend = ARM_BACKENDS[arm]()
        per_task: list[dict[str, Any]] = []

        for task in tasks:
            if aborted:
                exclusions.append({"task_id": task.task_id, "arm": arm, "reason": "cost_ceiling_reached"})
                continue

            ingest_task(backend, task)
            retrieved = backend.recall(task.question, k=recall_k)
            prompt = build_prompt(task, retrieved)
            all_prompts.append(prompt)

            record: dict[str, Any] = {
                "task_id": task.task_id,
                "arm": arm,
                "metric": task.metric,
                "retrieved_chunks": len(retrieved),
                # Digest of the context this arm actually received. Compared
                # across arms after the run to find tasks where every arm saw
                # the same thing — see `degenerate_tasks` below.
                "context_digest": sha256_text("\n---\n".join(retrieved))[:16],
                "retrieval_hit_proxy": retrieval_hit(retrieved, task.answers),
                "official_score": None,
                "prediction": None,
                "judge_correct": None,
                "judge_score": None,
            }

            if scored:
                next_provider_cost = provider.estimate(prompt).cost_usd
                next_judge_cost = judge.estimate(task.question, task.answers, "").cost_usd
                if running_cost + next_provider_cost + next_judge_cost > effective_cost:
                    aborted = True
                    exclusions.append({"task_id": task.task_id, "arm": arm, "reason": "cost_ceiling_reached"})
                    per_task.append(record)
                    continue
                try:
                    completion = provider.complete(prompt)
                    running_cost += completion.usage.cost_usd
                    verdict = judge.judge(task.question, task.answers, completion.text)
                    running_cost += verdict.usage.cost_usd
                    latencies.append(verdict.latency_ms)
                    record["prediction"] = completion.text
                    record["official_score"] = METRICS[task.metric](completion.text, task.answers)
                    record["judge_correct"] = verdict.correct
                    record["judge_score"] = verdict.score
                except Exception as exc:  # noqa: BLE001 — one task's failure must not sink the run
                    failures.append({"task_id": task.task_id, "arm": arm, "error": str(exc)})

            per_task.append(record)

        hits = [r["retrieval_hit_proxy"] for r in per_task]
        scored_records = [r for r in per_task if r["official_score"] is not None]
        judged_records = [r for r in per_task if r["judge_correct"] is not None]
        results_by_arm[arm] = {
            "backend": backend.name,
            "task_count": len(per_task),
            "retrieval_hit_proxy_mean": (sum(hits) / len(hits)) if hits else None,
            "official_metric_mean": (
                sum(r["official_score"] for r in scored_records) / len(scored_records)
                if scored_records else None
            ),
            "judge_accuracy": (
                sum(1 for r in judged_records if r["judge_correct"]) / len(judged_records)
                if judged_records else None
            ),
            "tasks": per_task,
        }

    # A task whose whole haystack fits in one chunk hands every arm the same
    # context, so all three necessarily score the same. That is a property of
    # the sample, not a finding about Zeref, and counting it as a three-way tie
    # silently drags every arm's mean toward the others. ConvoMem is ~37%
    # such tasks. Report them so a comparison can be read with them excluded.
    degenerate: list[str] = []
    if len(arm_names) > 1:
        by_task: dict[str, set[str]] = {}
        for arm_result in results_by_arm.values():
            for record in arm_result["tasks"]:
                by_task.setdefault(record["task_id"], set()).add(record["context_digest"])
        degenerate = sorted(tid for tid, digests in by_task.items() if len(digests) == 1)
        for arm_result in results_by_arm.values():
            degenerate_set = set(degenerate)
            for record in arm_result["tasks"]:
                record["identical_context_across_arms"] = record["task_id"] in degenerate_set
            discriminating = [
                r for r in arm_result["tasks"] if not r["identical_context_across_arms"]
            ]
            # NB: do not name these `scored` — that is the boolean parameter
            # deciding whether this is a scored or proxy run, and shadowing it
            # with a (possibly empty, therefore falsy) list silently relabels
            # the whole run as proxy mode.
            judged_disc = [r for r in discriminating if r["judge_correct"] is not None]
            scored_disc = [r for r in discriminating if r["official_score"] is not None]
            arm_result["discriminating_task_count"] = len(discriminating)
            arm_result["judge_accuracy_discriminating"] = (
                sum(1 for r in judged_disc if r["judge_correct"]) / len(judged_disc)
                if judged_disc else None
            )
            arm_result["official_metric_mean_discriminating"] = (
                sum(r["official_score"] for r in scored_disc) / len(scored_disc)
                if scored_disc else None
            )

    prompts_hash = sha256_text(PROMPT_TEMPLATE + "\n\x00".join(all_prompts))
    model_id = provider.model_id if provider is not None else "none (proxy mode, no provider)"
    judge_model = judge.model_id if judge is not None else None
    avg_latency_ms = (sum(latencies) / len(latencies)) if latencies else None
    # Report the REAL accumulated usage. Hardcoding estimated=True here would
    # stamp a live scored run as an estimate, which is exactly the kind of
    # provenance error that makes a published number indefensible. A run counts
    # as estimated only when it never made a live call: proxy mode, a dry-run
    # provider, or a judge that only estimates.
    provider_estimated = provider is None or getattr(provider, "dry_run", True)
    judge_estimated = judge is None or not getattr(judge, "_live", False)
    # Deltas, not lifetime totals: a provider instance accumulates across every
    # run it is passed to, so reporting its running total would attribute an
    # earlier run's tokens to this one.
    usage_total = {
        "input_tokens": (getattr(provider, "total_input_tokens", 0) - tokens_in_at_start) if provider else 0,
        "output_tokens": (getattr(provider, "total_output_tokens", 0) - tokens_out_at_start) if provider else 0,
        "cost_usd": round(running_cost, 6),
        "estimated": (not scored) or provider_estimated or judge_estimated,
    }

    return {
        "label": (
            "SCORED RUN" if scored else "PROXY RUN — infrastructure check only. "
            "No model was called; retrieval_hit_proxy is not the benchmark's "
            "official metric and no external benchmark score is claimed."
        ),
        "benchmark": benchmark,
        "arms": list(arm_names),
        "mode": "scored" if scored else "proxy",
        "task_count": len(tasks),
        "aborted": aborted,
        "max_cost_usd": effective_cost,
        "max_cost_clamped_to_ceiling": clamped,
        "cost_estimate": cost_estimate.to_dict() if cost_estimate is not None else None,
        # Tasks where every arm received identical context and therefore
        # cannot discriminate between arms. Read `*_discriminating` metrics
        # alongside the headline means; a large count here means the headline
        # comparison is mostly measuring tasks that could not tell the arms
        # apart.
        "degenerate_task_ids": degenerate,
        "degenerate_task_count": len(degenerate),
        "chunk_target_chars": CHUNK_TARGET_CHARS,
        "results_by_arm": results_by_arm,
        "provenance": build_provenance(
            loader, data_path, model_id, prompts_hash, usage_total,
            mode="scored" if scored else "proxy",
            judge_model=judge_model,
            seed=seed,
            avg_latency_ms=avg_latency_ms,
            failures=failures,
            exclusions=exclusions,
        ),
    }


def write_results(path: str | Path, payload: dict[str, Any]) -> Path:
    from benchmarks.external.harness import write_results as _write
    return _write(path, payload)
