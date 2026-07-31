# Shiroe — Wiki

> Imagine you are an **architect** on a major building, and every morning a different contractor shows up. Before anyone lays a brick you re-explain the blueprint, the constraints, the decisions you and the last contractor made, and what is already built. Every conversation starts from zero.
>
> That is what working with AI assistants is like. Each new session starts blind, and context evaporates when the window closes.
>
> **Shiroe is a local-first AI work control plane for AI agents.** Project memory lives in your repository as files you can read and diff. Sessions read it before they act, write to it through a guarded path, and hand it to the next session cleanly. The memory travels with the project, not with the tool.

## Read these first

- **[[Architecture]]** — how the pieces fit and what each one guarantees
- **[[Memory-Model]]** — the store invariant, boundary-first reads, contradiction handling
- **[[Privacy-Model]]** — modes, redaction classes, fail-closed export
- **[[Installation]]** — setup and verification
- **[[FAQ]]** — direct answers to common questions

## Reference

- **[[Team-Packs]]** — on-demand multi-agent configurations
- **[[Pattern-Detection]]** — how repeated work becomes a reviewable draft
- **[[Glossary]]** — canonical terms
- **[[Stack]]** — projects Shiroe routes alongside
- **[[Inspirations]]** — engineering lineage

## The two properties worth understanding

Most memory tools store text and retrieve it. Two design decisions separate Shiroe from that baseline, and both are enforced in code rather than described in prose.

**Reads are boundary-first.** A session does not load a project to answer a question about the project. It reads `memory/hot.md`, consults `memory/index.md` only if hot is insufficient, then loads a single named section of a single named page. Read cost tracks the question, not the age of the project. See [[Memory-Model]].

**Contradictions go to a human.** When a new claim conflicts with a stored one, the write halts, both sides are recorded with their provenance, and the conflict waits for you. Shiroe refuses to settle it by recency, by evidence grade, by dropping one side quietly, or by deferring forever — each of those makes a judgment call while appearing not to. See [[Memory-Model]].

## What the engine does

| Capability | Behavior |
|---|---|
| Guarded writes | Fact, evidence, privacy, and contradiction checks run before a write gate admits a claim. |
| Boundary-first recall | Hot file → index → named page section. |
| Contradiction detection | Structured conflict surfacing with human arbitration; never auto-resolved. |
| Evidence grading | Source quality graded separately from deliberation quality. |
| Deterministic redaction | Regex plus NFKC normalization, homoglyph folding, base64 decoding. |
| Cross-tool handoff | Scrubbed, fail-closed artifacts for five targets. |
| Release gating | Tests and internal benchmarks execute live; trust override requires a matching commit. |
| Reasoning-class routing | Criticality resolves to a class; a provider descriptor resolves the model at the edge. |

## Honest posture

- **Shiroe performs no inference.** Your harness calls the model.
- **No benchmark scores are published.** Loaders for five public suites are scaffolded; no runs have been performed. See [[Architecture]].
- **MIT licensed, no warranty.** The privacy scrubber is defense-in-depth, not a licence to paste production credentials into prompts.

## Where to start

| If you want to… | Read |
|---|---|
| Install and verify | [[Installation]] |
| Understand the system | [[Architecture]] → [[Memory-Model]] |
| Lock down privacy first | [[Privacy-Model]] |
| See how multi-agent work is configured | [[Team-Packs]] |
| Get a straight answer to one question | [[FAQ]] |

---

[`README`](https://github.com/kanadhiayash/shiroe) · [`AGENTS.md`](https://github.com/kanadhiayash/shiroe/blob/main/AGENTS.md) · [`SECURITY.md`](https://github.com/kanadhiayash/shiroe/blob/main/SECURITY.md) · [`CONTRIBUTING.md`](https://github.com/kanadhiayash/shiroe/blob/main/CONTRIBUTING.md)
