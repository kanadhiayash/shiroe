# External benchmark harness — honest methodology

**No external benchmark scores are claimed until full-dataset runs are
published.** Everything in this directory is infrastructure (WS5 Phase A).
The numbers produced by the internal quality axes (`benchmarks/run-all.py`)
are fixture-based self-checks and are NOT external benchmark results.

## What this is

A reproducible, provenance-bound harness for running the Shiroe AI Tactician
and two honest baselines against real external datasets:

- Supported: **LoCoMo, LongMemEval, ConvoMem, PersonaMem, RULER, HELMET**
  (`loaders/`). ConvoMem's field names were built to the common `Task` shape
  and have not been checked against a live download (no-network-fetch
  constraint when this loader was built) — verify before pinning its hash.
- Explicitly unsupported, with reasons: see [`UNSUPPORTED.md`](UNSUPPORTED.md).
- Baselines (`baselines/`): `plain_files` and `sqlite_fts` are legacy
  infrastructure checks. The three arms every scored run reports are
  `shiroe` (the real `shiroe.memory` search stack), `full_context` (no memory
  system — the honest floor), and `bm25` (a plain Okapi BM25 ranker).
  Phase B publishes shiroe numbers **next to** `full_context` and `bm25`
  or not at all.
- Providers (`providers/`): adapter interface with mandatory cost recording.
  The Anthropic adapter reads `ANTHROPIC_API_KEY` from the environment and in
  Phase A only supports dry-run token/cost estimation — live calls raise.
- Judges (`judges/`): `JudgeClient` interface for LLM-as-judge scoring.
  `GeminiJudgeClient` reads `GEMINI_API_KEY` from the environment or a
  gitignored `.env.local` at the repo root, never logs or stores the raw
  value, and only supports `estimate()` — live judging raises until a later
  authorized session enables it. `DeterministicFakeJudge` is the only judge
  ever exercised by this repo's tests.
- Cost gate (`cost.py`): `estimate_run_cost` computes judge-call count and
  dollar cost from the local dataset before anything runs; `shiroe benchmark
  external --live` refuses to proceed past the estimate without `--confirm`,
  clamps any `--max-cost` to a $500 hard ceiling, and the runner aborts
  mid-run — before the call that would cross the ceiling, not after — if the
  running total would exceed it.
- Runner (`runner.py`): `run_three_arms` drives all three arms per benchmark.
  `scored=False` (the CLI default, `--dry-run`) never calls a provider or
  judge. `scored=True` (`--live --confirm`) requires both.

## Downloading datasets (manual, never automatic)

No code here downloads anything. For each benchmark, follow the loader's
docstring (official source URL + file placement), then validate offline:

```bash
python3 -m benchmarks.external.loaders.locomo --check /path/to/locomo
python3 -m benchmarks.external.loaders.longmemeval --check /path/to/longmemeval
python3 -m benchmarks.external.loaders.convomem --check /path/to/convomem
python3 -m benchmarks.external.loaders.personamem --check /path/to/personamem
python3 -m benchmarks.external.loaders.ruler --check /path/to/ruler
python3 -m benchmarks.external.loaders.helmet --check /path/to/helmet
```

`--check` reports the dataset's sha256 so the hash can be pinned in the loader
(`PINNED_SHA256`) before any published run. A published result whose dataset
hash does not match the pin is invalid.

## Running (Phase A: dry-run only)

```bash
python3 -m benchmarks.external.harness \
  --benchmark locomo --data /path/to/locomo \
  --backend plain_files --provider anthropic --dry-run \
  --out benchmarks/external/results/locomo-dryrun.json
```

Dry-run ingests the haystack into the backend, performs recall, builds the
prompts, and estimates tokens/cost — with zero API calls. The only number it
produces is `retrieval_hit_proxy`, which is an infrastructure sanity signal,
not the benchmark's official metric, and must never be quoted as a score.

Every results JSON is bound to: git SHA, dataset name/version/sha256, model
id, prompts hash, token/cost record, timestamp, and mode (`dry_run`/`live`).

## Three-arm CLI (`shiroe benchmark external`)

The single-backend `harness.py` invocation above still works for
infrastructure spot-checks. For an actual comparison, use the CLI, which
always runs the `shiroe`, `full_context`, and `bm25` arms together (a Shiroe
number alone is meaningless — see `shiroe/release/claim_gate.py`'s
`missing_baseline_pair` constraint):

```bash
# Default: proxy mode. Ingest + recall only, zero network calls.
shiroe benchmark external --benchmark locomo --data /path/to/locomo

# Cost estimate only — always printed before any run, live or not:
#   cost estimate: N tasks x 3 arms = ... judge calls, est. $X.XXXX
#   budget: $Y.YYYY

# Scored run (generates + judges an answer per task per arm). Requires
# --confirm and a cost estimate under --max-cost (hard ceiling: $500).
shiroe benchmark external --benchmark locomo --data /path/to/locomo \
  --live --confirm --max-cost 5 --judge gemini
```

`--live` without `GEMINI_API_KEY`/live client support still makes zero
network calls: `GeminiJudgeClient.judge()` raises until a later authorized
session enables it, and the runner records that as a per-task failure in
`provenance.failures` rather than crashing the run. Provenance also records
`judge_model`, `seed`, `avg_latency_ms`, and `exclusions` (tasks skipped
because the running cost hit `--max-cost` mid-run).

## What Phase B will publish (budget-gated)

- Full-dataset runs of shiroe AND both baselines with the same provider,
  prompts, and recall budget, scored by each benchmark's own metric
  (exact match / token F1 / choice accuracy as defined per loader).
- Provenance for every number: dataset hash pinned, git SHA, model id,
  prompts hash, and the real (not estimated) token/cost record.
- Failures and losses included — if a baseline beats shiroe on an axis, that
  is published too.

Until those runs exist, the only honest claim is: "the harness exists and the
loaders validate the datasets". Nothing here supports a ranking claim.
