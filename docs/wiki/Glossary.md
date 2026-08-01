# Glossary

Canonical terms used across Shiroe documentation. Where a term names a code construct, the module is cited.

## Memory and reads

**Boundary file** — A file whose job is to bound a read. `memory/hot.md` is the first boundary (current context, kept short); `memory/index.md` is the second (a domain index). Reading stops at the smallest boundary that answers the question.

**Boundary-first read** — The read discipline: `hot.md`, then `index.md` if hot is insufficient, then one named section of one named page. Never load a full page to scan it. Read cost tracks the question, not the project's age.

**Canonical store invariant** — The single answer to "what is source of truth": SQLite holds canonical current state, JSONL holds canonical append-only history, Markdown is a generated human-readable view, TOON is an optional generated model-input view. Generated files carry a do-not-edit header. See `docs/adr/ADR-0001-canonical-store.md`.

**Atom** — A single stored unit of memory carrying content, provenance, and a privacy class.

**Snapshot** — A point-in-time copy of memory state with a manifest, written at session close.

## Writes and guards

**Guarded write path** — The fixed sequence every write passes: `fact_guard` → `evidence_guard` → `privacy_guard` → `contradiction_guard` → `write_gate`. A claim failing any guard does not reach the store. Modules in `shiroe/guards/`.

**Write gate** — The final admission check. Nothing enters the store without clearing it.

**Single-writer** — Only one writer may modify a memory resource at a time, enforced by an advisory lock in `shiroe/lock.py`. A second concurrent writer aborts with a clear error.

**Human arbitration** — The requirement that a detected contradiction be resolved by a person. Shiroe surfaces both sides with provenance and waits.

**Refused resolutions** — The four shortcuts contradiction handling will not take: recency-wins, grade-wins, silent-drop, indefinite-snooze. Each decides the question while appearing not to.

**Evidence quality** — A grade on the *source*: provenance, directness, recency, authority, corroboration, reproducibility, known contradictions.

**Review robustness** — A grade on the *deliberation*: method diversity, independent agreement, recorded dissent, counterarguments. Stored separately from evidence quality; reviewer agreement never upgrades weak source evidence.

## Privacy

**Privacy mode** — One of `exact` (verbatim), `abstract` (strip PII, internal paths, credentials — the default), or `local-only` (block all external transmission). Set in root `PRIVACY.md`.

**Privacy class** — The export classification on an atom: `public-safe`, `private`, `unknown`, or `local-only`.

**Fail-closed export** — The export rule: only `public-safe` exports by default; `unknown` is treated exactly like `private` so unclassified content cannot leak by omission; `local-only` never exports under any flag.

**Deterministic redaction** — Redaction performed by code rather than model judgment. Input is NFKC-normalized, homoglyphs folded to ASCII, and base64 payloads decoded before pattern matching.

## Routing

**Reasoning class** — The provider-neutral cost and capability tier a task is entitled to. Core code and schemas name only the class, never a vendor model ID. Defined in `shiroe/core/reasoning.py`.

- `fast` — cheapest class; the entitlement for LOW-criticality tasks.
- `balanced` — default working tier for MEDIUM criticality.
- `deep` — higher-cost tier for HIGH criticality.
- `frontier` — top-cost tier, CRITICAL-only, enforced by `ReasoningPolicyError` rather than by prose.
- `local` — placement constraint: run on-device. Not a cost tier; permitted at any criticality.
- `private` — placement constraint: run in a privacy-restricted context. Not a cost tier; permitted at any criticality.

**Criticality** — A task's declared weight: LOW, MEDIUM, HIGH, or CRITICAL. Resolves to the reasoning class the task is entitled to. A request may downgrade to a cheaper class but never upgrade.

**Provider adapter** — The only place a concrete vendor model ID may appear: a declarative `<provider>.json` file in `shiroe/adapters/providers/` mapping each reasoning class to a model ID and optional effort. Loaded by `JsonProviderAdapter`. Descriptors ship for `anthropic` and `openai`. Adding a provider is a config file, not a code change. Shiroe does not itself call model APIs.

**Harness** — The external AI CLI or IDE surface Shiroe plugs into. Shiroe is not a harness; it is the memory and governance layer a harness reads and writes through.

**Harness adapter** — A module implementing detect, health, and context-export for one harness. Registered adapters: `claude-code`, `codex`, `gemini-cli`, `hermes`, `kimi-code`, `odysseus`, `grok`.

**Enforcement level** — The honesty label on how strongly Shiroe can govern an integration, never claimed beyond what the execution path supports.

- **Embedded** — Shiroe authorizes operations through native hooks, plugins, lifecycle callbacks, or controlled subprocesses.
- **Sidecar / proxy** — Shiroe enforces only work routed through its own CLI, MCP server, API, or proxy.
- **Context-only** — Shiroe supplies context and instructions but cannot guarantee enforcement.

## Handoff

**Handoff artifact** — A compiled, privacy-scrubbed package that carries project state into the next session or tool.

**Handoff target** — One of the five supported destinations: `codex`, `claude`, `cursor`, `github`, `human`.

## Extension

**Team pack** — An on-demand configuration declaring active agents, permitted skills, and budget envelope. Role packs (`solo`, `build`, `research`, `red`, `audit`, `ship`) describe the shape of work; size packs (`small`, `medium`, `enterprise`) set the cost envelope. Defined in `team-packs/`.

**Two-Strikes Rule** — Do not codify a rule on the first occurrence of an error. Log it; wait for the second. One occurrence is noise, two is a pattern, and premature codification produces brittle rules.

**Review-first extension** — New skills are drafted for human review in `skills/drafts/` and never auto-activated.

**Component status** — The capability label every component carries: `runtime` (executing code with test coverage), `adapter` (a thin declarative bridge), `contract` (a schema or spec, not necessarily runtime-backed), `experimental` (implemented, not yet past its acceptance threshold).

## Benchmarks

**Internal quality axis** — A score the deterministic suite assigns this repository against its own rubric, used as a release gate. Not a benchmark ranking and not comparable to another system's numbers.

**External benchmark loader** — Scaffolding that reads a public benchmark's data format. Loaders exist for LoCoMo, LongMemEval, PersonaMem, RULER, and HELMET. No dataset runs have been performed and no scores exist.

**Release gate** — A check that must pass before release. Gates execute the test and benchmark suites live rather than reading a stored verdict.

**Commit binding** — The requirement that an independent trust re-grade name the commit it graded. If the recorded commit does not match `HEAD`, the override is refused and the deterministic draft publishes instead.

## Related

- [[Architecture]] — how these fit together
- [[Memory-Model]] — store and read discipline
- [[Privacy-Model]] — modes and classes
