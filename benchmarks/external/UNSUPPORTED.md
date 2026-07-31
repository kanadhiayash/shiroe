# Requested-but-unsupported benchmarks

Every benchmark that was requested for the Shiroe program but is NOT supported
by this harness, with the reason. Nothing is silently omitted. Availability
claims below are **unverified — pending availability check** (as of 2026-07);
each will be re-verified before Phase B publishes anything.

| Benchmark | Reason unsupported |
|---|---|
| BEAM-1M | 1M-token tier of BEAM; no reproducible public harness/data release confirmed for this tier (unverified — pending availability check). |
| BEAM-10M | 10M-token tier of BEAM; same as BEAM-1M, and context sizes exceed any Phase B budget envelope (unverified — pending availability check). |
| MemoryAgentBench | Agent-environment benchmark requiring a tool-use sandbox; out of scope for this harness (unverified — pending availability check). |
| MemBench | No confirmed public dataset/harness release suitable for reproduction (unverified — pending availability check). |
| MEMPROBE | No public dataset/harness release located (unverified — pending availability check). |
| Memora/FAMA | No public dataset/harness release located (unverified — pending availability check). |
| LongMemEval-V2 | Not released as a distinct public dataset as of 2026-07; V1 is supported via `loaders/longmemeval.py` (unverified — pending availability check). |
| MemoryArena | Agent-vs-agent arena setup requiring an interactive environment out of scope for this project (unverified — pending availability check). |
| Mem2ActBench | Memory-to-action benchmark requiring an agent tool-execution sandbox; out of scope for this project (unverified — pending availability check). |
| EvoMemBench | No public dataset/harness release located (unverified — pending availability check). |
| PerMemBench | No public dataset/harness release located; persona coverage handled by PersonaMem (unverified — pending availability check). |
| MemEvoBench | No public dataset/harness release located; name overlaps EvoMemBench — possibly a variant of it (unverified — pending availability check). |
| MPBench (memory poisoning) | Adversarial memory-poisoning benchmark; requires an attack-injection harness that belongs in the security workstream, not the accuracy harness (unverified — pending availability check). |
| RGB | Retrieval-augmented generation robustness benchmark; measures RAG noise robustness, not long-term memory — out of scope (unverified — pending availability check). |
| AgentDAM | Agent data-minimization/privacy benchmark requiring a web-agent sandbox; out of scope for this harness (unverified — pending availability check). |

Supported benchmarks (loaders in `loaders/`): LoCoMo, LongMemEval, PersonaMem,
RULER, HELMET. The previously fixture-only adapters for BEAM and PersonaMem-v2
(`benchmarks/adapters.py`) remain internal fixture checks and are not external
benchmark support.
