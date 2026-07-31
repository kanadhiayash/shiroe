# Retrieval Internal Quality Axes

> **Internal quality axes — fixture-based self-checks. NOT external benchmark
> results.** External-dataset benchmarking lives in
> [`benchmarks/external/`](../benchmarks/external/README.md); no external
> scores are claimed until full-dataset runs are published.

Shiroe Memory Core retrieval is self-checked with deterministic local fixtures
in `benchmarks/fixtures/retrieval_cases.json` and `benchmarks/retrieval.py`.

## What Is Measured

- Continuity: keyword and entity search returns a stored decision.
- Privacy recall: raw provider-shaped credentials are scrubbed before storage
  and raw-secret search abstains.
- Contradiction: conflicting same-entity assumptions both remain retrievable.
- Freshness: an updated item returns its latest body and history event.
- Abstention: unrelated queries return an empty result set.
- External adapter fixtures: LoCoMo, LongMemEval, BEAM, PersonaMem, and
  PersonaMem-v2 fixture adapters run offline.

Every returned item must expose `source_ref`, `confidence`, `authority`, and
`why_returned` so recall is inspectable rather than magical.

## What Is Not Measured

- Semantic-vector recall.
- Hosted or cloud retrieval providers.
- Multi-user sync or CRDT behavior.
- Model prompt-injection quality after retrieval.
- Cross-project parent sync.
- Long-context compression quality.
- Full external-dataset performance for LoCoMo, LongMemEval, BEAM, PersonaMem,
  or PersonaMem-v2.

Those claims need separate fixtures and a new rubric version before they can be
advertised as benchmarked.

## Reproduce

```bash
python3 -m benchmarks.retrieval
python3 -m benchmarks.adapters
python3 benchmarks/run-all.py
```

See [`docs/BENCHMARK_ADAPTERS.md`](BENCHMARK_ADAPTERS.md) for adapter status
definitions and source links.
