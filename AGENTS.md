<!-- privacy-audit: allow-file "Canonical spec text. Names author (Yash Kanadhia) + describes credential/PII pattern classes AS spec content. All apparent PII/credential matches are documentation of what the scrubber detects, not leaks." -->

# AGENTS.md - Shiroe Canonical Spec

> **Naming note.** The product is **Shiroe**. The plugin and install
> identifier is `shiroe`.

This is the canonical agent specification for **Shiroe**. All harness-specific files (`CLAUDE.md`, `CODEX.md`, `GEMINI.md`, `LLAMA.md`, `.cursor/rules/shiroe.mdc`, `.windsurfrules`, `.aider.conf.yml`) defer to this document.

## Identity

Shiroe is a local-first AI work control plane. Harness-agnostic, model-agnostic, privacy-first. Per-project canonical wiki (flat `memory/` layout) + append-only pattern log + snapshots.

## First action every session (reading order — ZEREF_OS §0)

0. Read `SOUL.md` (5 operating principles — shapes every decision this session).
1. Read `config/PROJECT.md`. If missing, run `/start` (triggers project-setup interview).
2. Read `memory/hot.md` FIRST (≤500 words; current context).
3. Read `memory/index.md` if hot is insufficient (domain index).
4. Read `PRIVACY.md` (root) before any wiki write or tool use.
5. Read `REDACT.md` (root) before any external output.
6. Auto-load first 200 lines of `memory/MEMORY.md` (agent-written session notes).
7. Tail last 3 entries of `memory/patterns/PATTERNS.jsonl`.
8. Report: project, last session, active decisions, open questions, conflicts.

Shared safety rules (R1–R4) referenced from all skills: see `_shared/rules.md`.

Do NOT read individual wiki pages for general coding questions or things already in current project context.

## Core principles

1. **Local-first**: canonical state is markdown on disk; no hosted dependency
2. **Privacy-first**: every write passes through `privacy-guardian` (PRIVACY.md + REDACT.md + SHARING_POLICY.md)
3. **Boundary-first reads**: hot → index → page section, never full pages by default
4. **Human arbitration**: contradictions surface; never silently resolved
5. **Single-writer per resource**: only `memory-keeper` writes to wiki files
6. **Append-only logs**: `memory/patterns/PATTERNS.jsonl` is never edited
7. **Progressive activation**: minimal agents auto-load; rest lazy on trigger
8. **Evidence discipline**: separate facts / assumptions / unknowns / risks
9. **Token discipline**: `budget-governor` scales verbosity to model tier (Free / Standard / Enterprise)
10. **Review-first extension**: new skills are drafted to `skills/drafts/`, never auto-activated
11. **Two-Strikes Rule**: do not codify a rule on the first occurrence of an error. See `references/two-strikes-rule.md`.
12. **Harness Agnosticism**: AGENTS.md is source of truth; per-harness stubs defer. See `references/harness-translation-map.md`.
13. **Cost-Weight Auto-Gate**: `budget-governor` runs before every major task; CRITICAL / HIGH cannot proceed without stated tier. See `skills/budget-governor/SKILL.md` §Auto-Activation Rule.
14. **Task-Weight Reasoning Routing**: weight maps to a provider-neutral reasoning class — LOW→`fast`, MEDIUM→`balanced`, HIGH→`deep`, CRITICAL→`frontier`. `frontier` is CRITICAL-only; LOW never above `fast`. Concrete model ids live only in `shiroe/adapters/providers/`. See `## Reasoning-Class Routing` below.

## Auto-Activation Gates

Every major task passes these gates sequentially before any execution-model call. Each gate declares its result inline; user may override.

### Gate #1 — budget-governor

Classifies cost weight (CRITICAL / HIGH / MEDIUM / LOW), resolves active model tier, enforces weight ↔ tier match. CRITICAL never on Haiku; LOW flagged on Opus. Output line format:
`[budget-governor] weight=<W> tier=<T> match=<OK|MISMATCH> budget_remaining=$<n>`.

See `skills/budget-governor/SKILL.md`.

### Gate #2 — skill-router

Classifies task domain and pulls the smallest useful stack (1 lead + 2-3 support + 1 QA gate). Never activates all skills. Calls `fleet-activator` for any extended-tool hint. Output line format:
`[skill-router] domain=<D> lead=<L> support=[<s1>,<s2>] qa=<Q> ext=<E|none>`.

See `skills/skill-router/SKILL.md` and `skills/fleet-activator/SKILL.md`.

### Gate #3 — prompt-context-engine

Classifies the raw prompt (STRUCTURED / SEMI-STRUCTURED / UNSTRUCTURED). Rewrites UNSTRUCTURED prompts into a Structured Task Brief (`<objective>/<deliverable>/<constraints>/<context>/<success_criteria>`) with 30-second auto-approve. Zero context loss per `_shared/rules.md#R6`. Output line format:
`[prompt-context-engine] class=<C> action=<proceed|assume|restructure> brief_tokens=<n>`.

See `skills/prompt-context-engine/SKILL.md`.

## Reasoning-Class Routing

Per Core Principle 14. Weight (from `budget-governor`) maps to a provider-neutral
reasoning class (`shiroe/core/reasoning.py`). Provider adapters
(`shiroe/adapters/providers/<provider>.json`) map classes to concrete models at
the edge — core surfaces never name provider models.

| Weight | Reasoning class | Effort | Typical $ / task | Examples |
|---|---|---|---|---|
| **CRITICAL** | `frontier` | high | $0.50 – $5.00 | `pattern-to-skill` draft, parent-sync export, architecture decision |
| **HIGH** | `deep` | medium | $0.10 – $0.50 | `contradiction-resolution`, `handoff-compiler`, `project-setup` interview, `prompt-context-engine` restructure |
| **MEDIUM** | `balanced` | low / medium | $0.02 – $0.10 | `wiki-maintenance` consolidation, `evidence-grader` on 5-20 claims, `privacy-abstraction` rewrite |
| **LOW** | `fast` | low | < $0.02 | `budget-governor` gate, `capability-resolver` gate, `capability-prober` probe, single-fact lookup |

Placement classes `local` and `private` constrain where a task may run, not
how much it may spend; they are permitted at any weight.

### Cascade pattern (multi-step tasks)

```
orchestrator @ balanced          ← plans + decomposes
    ↓
executor @ balanced|fast by weight ← does the work per sub-task
    ↓
final gate @ frontier (high)      ← only when stakes warrant (irreversible writes, security, architecture)
```

Default: orchestrator on `balanced` — the cost-balanced default unless task
weight escalates or de-escalates. The top class exists for critical, ambitious
work only; everything routine rides the cheapest class that clears its QA gate.

### Hard constraints (enforced by `shiroe.core.reasoning.validate_request`)

- **LOW never above `fast`** — flag mismatch via `budget-governor` Step 4. Propose downgrade.
- **CRITICAL never below `balanced`; `frontier` reserved for CRITICAL** — hard block in code, not prose.
- **HIGH on `fast`** — warn, allow if user confirms. Common when budget is tight.
- **MEDIUM on `deep`** — warn, allow. Often the right call when stakes are unclear; `budget-governor` will log for retrospective tuning by `pattern-observer`.

### Per-skill routing audit (current state)

All skills' `reasoning_class` fields in `shiroe-registry.json` audited against weight per the matrix above. No LOW→`deep`+ or CRITICAL→`fast` mismatches detected. Borderline call: `privacy-abstraction` (`risk_level: high`, `reasoning_class: fast`) — kept on `fast` because redaction follows deterministic REDACT.md rules; bump to `balanced` if a future PATTERNS.jsonl event shows redaction misses on adversarial input. Tracked as forward signal for `pattern-observer`.

## Agents (6)

| Agent | Auto-load | Role |
|---|---|---|
| `memory-keeper` | yes | Single writer to flat `memory/`; reads, writes, logs |
| `privacy-guardian` | conditional | Enforces PRIVACY.md mode + REDACT.md classes + SHARING_POLICY.md allowlist |
| `sync-coordinator` | on `/start`/`/stop`/`/sync-parent` | Permissions, tool visibility, parent push |
| `evidence-curator` | conditional | Grades confidence, recency, provenance |
| `pattern-observer` | background | Watches `memory/patterns/PATTERNS.jsonl` for repeats |
| `handoff-orchestrator` | on `/stop` / model switch | Packages cross-harness handoff |

## Skills (15)

| Skill | Activation |
|---|---|
| `project-setup` | First `/start` or missing config |
| `wiki-maintenance` | After writes; consolidation |
| `contradiction-resolution` | When `memory-keeper` flags conflict |
| `privacy-abstraction` | Before writes when mode = abstract |
| `parent-sync` | Approved `/stop` or `/sync-parent` |
| `pattern-to-skill` | Threshold hit in `pattern-observer` |
| `memory-import-export` | Explicit migration request |
| `budget-governor` | Auto-gate #1: every major task, `/start`, tier change, budget warning |
| `skill-router` | Auto-gate #2: every major task, after budget gate |
| `fleet-activator` | Companion to `skill-router` when extended-tool hint present |
| `prompt-context-engine` | Auto-gate #3: every major task, after skill-router |
| `handoff-compiler` | Session end or model switch |
| `caveman-handoff` | Cross-model / cross-harness handoff compression (companion to `handoff-compiler`) |
| `evidence-grader` | On write, review, sync, conflict |

## Commands (8)

- `/start` — interview if first run; otherwise boot session, restore context (hot.md → index.md per §0)
- `/done` — write summary, persist decisions, refresh hot.md, conflict scan, append PATTERNS.jsonl, snapshot
- `/stop` — end session, optional parent sync, optional handoff compile
- `/status` — current state: project, active decisions, open questions, active team
- `/sync-parent` — manual parent rollup
- `/reset-permissions` — clear session overrides, restore defaults from PERMISSIONS + SHARING_POLICY
- `/review-skill` — review pattern-detected skill drafts in `skills/drafts/`
- `/team [solo|build|research|red|audit|ship]` — activate on-demand team pack (per ZEREF_OS §8)

## Memory model (flat layout per ZEREF_OS §12)

- `memory/hot.md` — last 3 sessions, ≤500 words (read first)
- `memory/index.md` — domain index (boundary file)
- `memory/DECISIONS.md` — confirmed decisions w/ provenance + evidence grade
- `memory/OPEN_QUESTIONS.md` — unresolved questions w/ owner
- `memory/RISKS.md` — identified risks w/ severity
- `memory/CONFLICTS.md` — contradiction queue (user arbitrates)
- `memory/MEMORY.md` — agent-written session notes (NOT human-edited)
- `memory/archive/` — superseded snapshots (never deleted per D9)
- `memory/patterns/PATTERNS.jsonl` — append-only tool/event log for pattern detection
- `memory/snapshots/<iso>/` — point-in-time wiki state + manifest
- `memory/raw/` — untouched source material
- `memory/sync/outbound/` — staged parent updates
- `memory/sync/parent/` — received parent updates

## Privacy & sharing (per ZEREF_OS §4)

Three root files:

- `PRIVACY.md` — modes (`exact` / `abstract` / `local-only`) — **default `abstract`**
- `REDACT.md` — concrete sensitive classes (credentials, pii, internal_paths, client_data, financial, proprietary_code)
- `SHARING_POLICY.md` — per-connector allowlist; **all OFF by default**

Every write to `memory/` and every external transmission passes through `privacy-guardian` per these files.

## Event log schema

```jsonl
{"ts": "2026-05-28T14:23:11Z", "agent": "memory-keeper", "event": "wiki-write", "target": "memory/DECISIONS.md", "payload": {"summary": "..."}, "hash": "sha256:...", "evidence_grade": "high"}
```

Fields: `ts` (ISO-8601 UTC), `agent`, `event`, `target` (path), `payload` (free), `hash` (sha256 of payload), `evidence_grade` (high/medium/low — optional).

## Permission model

See `config/PERMISSIONS.md` (filesystem / network / shell) and `SHARING_POLICY.md` (MCP / connectors).

```yaml
defaults:
  filesystem: [read-project, write-memory]
  network: [denied]
  mcp_servers: []      # see SHARING_POLICY.md for connector allowlist
session_overrides:
  # ephemeral; cleared by /reset-permissions or /stop
```

## Contradiction handling

When `memory-keeper` detects a conflict between an incoming write and existing wiki state:
1. Halt write
2. Append both sides to `memory/CONFLICTS.md`
3. Surface to user immediately OR snooze until `/done` (user choice)
4. User arbitrates; never silent resolution
5. Resolved entries move to `memory/DECISIONS.md` with both-sides provenance

## Pattern detection

`pattern-observer` runs background scan of `memory/patterns/PATTERNS.jsonl` over rolling 48–80h window (per ZEREF_OS §3.5 / D4). If ≥3 semantically similar events (n-gram similarity ≥ 0.8), surface as candidate skill via `pattern-to-skill`. Draft written to `skills/drafts/<draft-name>/SKILL.md`. User reviews via `/review-skill`. Never auto-activate.

## Team Packs (on-demand per ZEREF_OS §8)

| Team | Agents | Use |
|---|---|---|
| solo | 1 primary + Shiroe AI Tactician | default |
| build | Planner + Implementer + Reviewer | multi-module features |
| research | Investigator + Synthesizer + Fact-checker | tech evaluation |
| red | Attacker + Security reviewer + Constraint checker + Evidence recorder (read-only) | adversarial review |
| audit | Reader + Linter + Quality gate | pre-ship QA |
| ship | Changelog drafter + Release reviewer + Deploy verifier | release prep |

Max 4 agents per pack. Outputs land in `team/`. Activate via `/team [type]`. Definitions in `team-packs/`.

## Connector Advisory (per ZEREF_OS §9)

Shiroe ships with **zero** bundled MCP tools. Recommendation-only after `pattern-observer` detects repeated manual behavior. All connectors OFF by default in `SHARING_POLICY.md`. Recommended free stack documented in `references/connector-advisory.md`.

## Harness Translation Map (per ZEREF_OS §10)

| Harness | Stub | Load |
|---|---|---|
| Claude Code | `CLAUDE.md` | See @AGENTS.md |
| Codex | native | AGENTS.md |
| Cursor | `.cursor/rules/shiroe.mdc` | rules format → AGENTS.md |
| Gemini CLI / Antigravity | `GEMINI.md` | native AGENTS.md |
| Windsurf | `.windsurfrules` | rules format → AGENTS.md |
| Aider | `.aider.conf.yml.example` | convention-based |
| Hermes / Amp / Zed / Perplexity | native | AGENTS.md |

Full table + adding-a-harness procedure: `references/harness-translation-map.md`.

## What Shiroe is NOT (and what those mean)

- **Not itself a harness.** Shiroe plugs *into* the user's harness. It is the memory layer they read — not a replacement for the harness.
- **Not a hosted service.** No Shiroe server. Memory lives in local markdown in the project repo. Optional MCP connectors talk to hosted services only after explicit enable in `SHARING_POLICY.md`.
- **Not bundled with any MCP tools.** Recommendation-only. Never installs a connector on the user's behalf.
- **Not a sprawling skill catalog.** A small set of skills with strict triggers, not a large catalogue of specialists.
- **Not an always-on multi-agent panel.** Team packs are on-demand only and capped at 4 agents.
- **Not a persona.** Context + memory layer, not a simulated role.
- **Not dedicated to any single user or organization.** Free to install; use any model the user brings.
