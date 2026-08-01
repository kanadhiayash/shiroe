# Glossary

Canonical term definitions. Where a term names a code construct, the module is cited and the code is authoritative. If a term here conflicts with another doc, this file wins — file an issue against the other doc.

| Term | Definition |
|---|---|
| **Reasoning class** | Provider-neutral cost/capability tier a task is entitled to. Core code and schemas name only the class, never a vendor model id. Defined in `shiroe/core/reasoning.py`. |
| — `fast` | Cheapest class. Entitlement floor for LOW-criticality tasks; always available. |
| — `balanced` | Default working tier for MEDIUM-criticality tasks and routine orchestration. |
| — `deep` | Higher-cost tier for HIGH-criticality tasks needing more deliberation. |
| — `frontier` | Top-cost tier. CRITICAL-only, enforced in code by `ReasoningPolicyError` — no prose-only guardrail. |
| — `local` | Placement constraint: run on-device / offline. Not a cost tier; permitted at any criticality. |
| — `private` | Placement constraint: run in a privacy-restricted execution context. Not a cost tier; permitted at any criticality. |
| **Provider adapter** | The only place a concrete vendor model id may appear. A declarative `<provider>.json` file (`shiroe/adapters/providers/`) mapping each reasoning class to a model id + effort for one provider. Loaded via `JsonProviderAdapter` and resolved with `resolve_model()`. |
| **Harness** | The external AI CLI/IDE surface Shiroe plugs into. Registered harness adapters: `claude-code`, `codex`, `gemini-cli`, `hermes`, `kimi-code`, `odysseus`, `grok`. Shiroe is not itself a harness — it is the memory/governance layer a harness reads and writes through. |
| **Capability** | Any external unit of specialist execution Shiroe can discover and govern: skill, agent, plugin, MCP server, CLI, repository tool, script, workflow, evaluator, or API service. |
| **Capability lifecycle states** | The only path from discovery to execution. No state may be skipped and no execution happens before `approved`. |
| — `discovered` | Found by a discovery-root scan; not yet inspected. |
| — `quarantined` | Held pending inspection; the default state for anything newly discovered or whose digest changed. |
| — `inspected` | Manifest parsed/inferred, secrets and permission scan complete, trust report produced. |
| — `approved` | Explicitly granted execution trust by an approval source (user or approved policy). |
| — `benchmarked` | Has at least one recorded benchmark result informing selection scoring. |
| — `active` | Currently eligible for selection into compiled teams. |
| — `stale` | Approved/benchmarked but not refreshed within policy freshness window; excluded from selection until refreshed. |
| — `revoked` | Trust withdrawn; execution blocked until re-approved. |
| — `compromised` | Failed a trust or security check; blocked and flagged for review. |
| **Mission blueprint** | A schema (`shiroe.mission/v1`) declaring the functional seats, required outputs, execution graph, and completion criteria for a task type (e.g. `build`, `research`, `red`, `audit`, `ship`, `solo`). Defines *what* is needed, never *who* by fixed name. |
| **Execution policy** | A named envelope controlling cost, parallelism, assurance, and autonomy for a compiled team. Envelopes ship as size team packs in `team-packs/`: `small` (tightest budget, lowest default tier, memory writer only), `medium` (typical project work, top tier reserved for critical-weight tasks), `enterprise` (widest budget, all background agents, adversarial verification panels enabled). An envelope raises the cost ceiling; it does not grant capability, and reasoning-class entitlement still applies. |
| **Compiled team** | The concrete, persisted plan produced by matching a mission blueprint against approved capabilities under an execution policy: seat assignments, versions/digests, permissions, execution graph, retry/timeout/stop rules, verification requirements, cost envelope, and codec selection. |
| **Enforcement level** | The honesty label on how strongly Shiroe can actually govern a given integration — never claimed beyond what the active execution path supports. |
| — `A` — Embedded | Shiroe intercepts or authorizes operations through native hooks, plugins, lifecycle callbacks, or controlled subprocesses. |
| — `B` — Sidecar/Proxy | Shiroe can enforce only work explicitly routed through its own CLI, MCP server, API, or proxy. |
| — `C` — Context-only | Shiroe can generate instructions and memory context but cannot guarantee enforcement. |
| **Canonical store invariant** | The single resolved answer to "what is source of truth": SQLite holds canonical current state; JSONL holds canonical append-only history; Markdown is a generated human-readable view; TOON is an optional generated model-input view. Generated files carry a `DO NOT EDIT DIRECTLY` header. See `docs/adr/ADR-0001-canonical-store.md`. |
| **Evidence quality vs. review robustness** | Two distinct, separately stored scores. Evidence quality grades the *source* (provenance, directness, recency, authority, corroboration, reproducibility, contradictions). Review robustness grades the *deliberation* (method diversity, independent agreement, dissent, counterarguments). Council/jury agreement must never automatically upgrade weak source evidence to a strong grade. |
| **Autonomy modes** | How much a compiled team executes without a stop. |
| — `suggest` | Compile only; nothing executes automatically. |
| — `auto-safe` | Default. Executes local, reversible, already-approved actions automatically. |
| — `policy-bound` | Executes everything the active policy allows and stops only at a denied boundary. |
| | All three modes always stop for the hardcoded `ALWAYS_REQUIRE_APPROVAL` list (see `docs/adr/ADR-0005-policy-precedence.md`) regardless of mode. |
| **Component status taxonomy** | The label every component and registry entry must carry so nothing claims capability it doesn't have. |
| — `runtime` | Backed by executing code with test coverage. |
| — `adapter` | A provider/harness/capability bridge — thin, declarative, swappable. |
| — `contract` | A schema, manifest, or markdown spec describing required behavior not yet (or not necessarily) runtime-backed. |
| — `experimental` | Implemented but not yet benchmarked past its acceptance threshold; may regress or be removed. |
