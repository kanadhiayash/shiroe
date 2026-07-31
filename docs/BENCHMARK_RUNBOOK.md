# External benchmark runbook

How to run scored external benchmarks locally. Written for a VS Code terminal.

Everything here is opt-in and explicit. The harness never downloads anything on
its own, and never makes a live call without `--live --confirm`.

---

## Before you start

**1. Key.** A live run needs `GEMINI_API_KEY` in a gitignored `.env.local` at the
repo root, or exported in the shell. The tooling reports only whether a key was
found, never its value. Confirm without printing it:

```bash
python3 -c "import sys; sys.path.insert(0,'.'); from benchmarks.external.judges.gemini import GeminiJudgeClient; print('key found:', GeminiJudgeClient().has_key())"
```

**2. Data.** Datasets live outside the repo, by default `~/zeref-benchmark-data`.
Override with `ZEREF_BENCHMARK_DATA`. Fetch (resumable — re-running skips files
already present):

```bash
python3 scripts/fetch-benchmark-data.py --all
```

**3. Verify each dataset before spending anything.** This is offline and free:

```bash
python3 -c "
import sys; sys.path.insert(0,'.')
from pathlib import Path
from benchmarks.external.loaders import locomo, longmemeval, convomem
root = Path.home()/'zeref-benchmark-data'
for m, name in ((locomo,'locomo'), (longmemeval,'longmemeval'), (convomem,'convomem')):
    c = m.check(root/name)
    print(f'{name}: ok={c.ok} tasks={c.task_count} pinned_match={c.sha256_actual==c.sha256_pinned}')
"
```

A `checksum mismatch` here means your local copy is not the pinned release.
Investigate before running — do not pin over it to make the message go away.

---

## Dry run first, every time

Dry run is the default: ingest and recall only, zero network calls, no cost. It
prints the cost estimate a live run *would* incur.

```bash
python3 -m shiroe.cli benchmark external --benchmark locomo --data ~/zeref-benchmark-data/locomo --arms all --limit 20
```

Read the `cost estimate:` line before going further. If that number surprises
you, stop.

---

## Scored run

Requires `--live --confirm`, and the estimate must fit under `--max-cost`.

Start small and confirm the pipeline end to end:

```bash
python3 -m shiroe.cli benchmark external --benchmark locomo --data ~/zeref-benchmark-data/locomo --arms all --limit 20 --live --confirm --max-cost 2 --out results/locomo-smoke.json
```

Then the full dataset:

```bash
python3 -m shiroe.cli benchmark external --benchmark locomo --data ~/zeref-benchmark-data/locomo --arms all --live --confirm --max-cost 60 --out results/locomo-full.json
```

### `--max-cost` is PER INVOCATION, not global

This is the one thing most likely to cost real money unexpectedly. The budget
ceiling is enforced inside a single command. Three terminals running with
`--max-cost 60` can spend **$180** in total, not $60 — nothing coordinates
between processes.

If you run benchmarks in parallel terminals, divide the budget yourself and set
each `--max-cost` to its own share.

The `$500` figure in `cost.COST_CEILING_USD` is a hard clamp on what any single
invocation may request. It is not a total spend cap across runs.

---

## Running several benchmarks in parallel

Safe to run in separate terminals — different datasets, separate output files,
no shared state. One benchmark per terminal:

```bash
# terminal 1
python3 -m shiroe.cli benchmark external --benchmark locomo --data ~/zeref-benchmark-data/locomo --arms all --live --confirm --max-cost 60 --out results/locomo.json

# terminal 2
python3 -m shiroe.cli benchmark external --benchmark longmemeval --data ~/zeref-benchmark-data/longmemeval --arms all --live --confirm --max-cost 60 --out results/longmemeval.json

# terminal 3
python3 -m shiroe.cli benchmark external --benchmark convomem --data ~/zeref-benchmark-data/convomem --arms all --live --confirm --max-cost 60 --limit 500 --out results/convomem.json
```

Do **not** run the same benchmark in two terminals expecting it to go faster.
There is no work-sharing; you would pay twice for the same tasks.

ConvoMem is ~75,000 QA pairs. Always pass `--limit` unless you have decided,
deliberately, to score the whole thing.

---

## All three arms, always

`--arms all` runs `zeref`, `full_context`, and `bm25`.

A Zeref-only number is unfalsifiable. Plain full-context beats several
purpose-built memory products on their own published numbers, and a lexical
BM25 ranker is a genuinely strong baseline on LoCoMo. If Zeref loses to either,
that is the result — publish it. Do not narrow `--arms` to the one that looks
best, and do not adjust the rubric after seeing scores.

---

## Rate limits

Free-tier Gemini keys have per-minute and per-day request caps. A large run can
hit them; `gemini-2.0-flash` already returns 429 on this key. The judge retries
transient 429/5xx with backoff, then fails that task and records it in
`provenance.failures` rather than silently scoring it correct.

If a run shows many failures, check the rate limit before trusting the numbers —
a throttled run scores every failed task as incorrect, which penalises whichever
arm happened to be running when the limit hit.

---

## Reading results

Output JSON carries per-arm `judge_accuracy`, `official_metric_mean`, and
`retrieval_hit_proxy_mean`, plus a `provenance` block with dataset hash, model
ids, seed, prompt hash, token usage, and every failure and exclusion.

`retrieval_hit_proxy` is **not** an official benchmark metric. It is an
infrastructure signal only. Never quote it as a benchmark score.

Cost in `provenance.usage_total` is derived from a local pricing table. Verify
against current published pricing before quoting any dollar figure publicly.

---

## Claims discipline

No external benchmark number has been published for this project. Until one is,
the correct public posture is "explicitly unscored", enforced by
`shiroe/release/claim_gate.py`.

When results exist, report the arm comparison, the dataset revision, the judge
model, and the sample size together. A score without those four is not a result.
