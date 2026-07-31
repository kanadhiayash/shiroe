---
name: research
agents: 3
max_agents: 4
read_only: false
description: Investigator + Synthesizer + Fact-checker. For architecture decisions and tech evaluation.
output_dir: team/
---

# research team pack

> Sourced from SHIROE_OS §8.

## Roster

| Role | Responsibility |
|---|---|
| **Investigator** | Gathers raw material: web sources, code samples, docs, benchmarks. Writes to `team/research-raw.md`. |
| **Synthesizer** | Distills the raw material into the decision dimensions, trade-offs, recommendations. Writes `team/research-synthesis.md`. |
| **Fact-checker** | Adversarial verification of Synthesizer's claims. Hunts for contradicted sources, missing context, stale data. Writes `team/research-verification.md`. |

## When to use

- Architecture choices (framework, DB, infra)
- Tech evaluation ("should we use X?")
- Comparative analysis (X vs Y vs Z)
- Migration decisions

## Activation

`/team research`

## Outputs

| File | Owner |
|---|---|
| `team/research-raw.md` | Investigator |
| `team/research-synthesis.md` | Synthesizer |
| `team/research-verification.md` | Fact-checker |

## Rules

- Investigator must cite every source with URL + retrieval date.
- Synthesizer must NOT make claims absent from `team/research-raw.md`.
- Fact-checker must score each major claim as `confirmed`, `refuted`, or `uncertain`.
- Final decision recorded in `memory/DECISIONS.md` only after Fact-checker pass.
- `evidence-curator` grades the final decision based on Fact-checker output.

## Anti-hallucination

This team consumes `references/shared-anti-hallucination.md`. Fact-checker has explicit instruction to refute by default when uncertain (per `references/shiroe-qa-gate.md`).
