# Benchmark Adapters (fixture-only — internal quality axes)

> **Internal quality axes — fixture-based self-checks. NOT external benchmark
> results.** These adapters only prove Shiroe can run offline fixtures shaped
> like each benchmark family. Real external-dataset loaders, baselines, and
> the provenance-bound harness live in
> [`benchmarks/external/`](../benchmarks/external/README.md).

Shiroe includes fixture-first adapter interfaces for:

- LoCoMo: https://github.com/snap-research/locomo
- LongMemEval: https://github.com/xiaowu0162/longmemeval
- BEAM: https://github.com/mohammadtavakoli78/BEAM
- PersonaMem: https://github.com/bowen-upenn/PersonaMem
- PersonaMem-v2: https://github.com/bowen-upenn/PersonaMem-v2

Default tests do not download external datasets. They only prove that Shiroe can
run an offline fixture shaped like each benchmark family.

Adapter statuses:

- `not_configured`: fixture or adapter metadata is missing.
- `fixture_pass`: the offline fixture passed.
- `full_dataset_pending`: the adapter exists but a full external dataset run has
  not passed.
- `verified`: a dated, reproducible full-dataset run passed locally.

Current public-safe status: fixture adapters pass locally; full external dataset
verification is pending and must not be described as ranking performance.
