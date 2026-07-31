# MODEL_DEBATE.md — What Each AI Model Needs From Shiroe

> Synthesized from research across Claude/Anthropic, OpenAI/GPT, Google/Gemini, and open-source model behavior documentation (May 2026).

---

## The Six Things Every Model Agrees On

1. Lean metadata at session start (not a wall of text)
2. Deep context on-demand (retrieved, not always-loaded)
3. External memory on disk (not in-context at all times)
4. Minimal tool count with high-leverage primitives
5. Deterministic scripts for reliability
6. Clear success criteria (declarative goals, not imperative steps)

Shiroe satisfies all six through hot.md startup, AGENTS.md lean protocol, token budget layer, connector advisory, and skill recommendation system.

---

## Claude (Anthropic) — Requirements Ranked by Priority

| Priority | Requirement | Shiroe Solution | Rating /10 |
|----------|------------|----------------|-----------|
| 1 | Lean context loading (≤250 lines CLAUDE.md) | CLAUDE.md = 1 line stub pointing to AGENTS.md | 10 |
| 2 | Persistent memory across sessions | memory/hot.md + MEMORY.md auto-loaded | 10 |
| 3 | Anti-sycophancy modes (Challenge / Steel-Man) | Defined in SHIROE_OS.md Section 2 | 9 |
| 4 | Read/write memory separation | AGENTS.md (human) + MEMORY.md (agent-written) | 10 |
| 5 | Subagent context isolation | Team packs spawn with separate context windows | 9 |
| 6 | PreToolUse hooks for red lines | Red team pack + PRIVACY.md + REDACT.md gates | 8 |
| 7 | Two-Strikes rule for file hygiene | Defined in SHIROE_OS.md Anti-Patterns | 10 |
| 8 | Rule lifecycle (active/dormant/dead) | skills/drafts/ + CONFLICTS.md supersession | 9 |
| 9 | Path-scoped rules (zero token cost) | AGENTS.md + per-skill YAML frontmatter option | 8 |
| 10 | Privacy-first output | PRIVACY.md + REDACT.md pre-write check | 10 |

**Claude-specific gaps Shiroe fixes:** Starts every session from zero (hot.md), sycophantic drift (challenge-first mode), CLAUDE.md rot (Two-Strikes rule).

---

## GPT-4o / OpenAI Models — Requirements Ranked by Priority

| Priority | Requirement | Shiroe Solution | Rating /10 |
|----------|------------|----------------|-----------|
| 1 | Stable context prefix for prompt caching | AGENTS.md stable header structure | 9 |
| 2 | Append-only session history | PATTERNS.jsonl + MEMORY.md append model | 9 |
| 3 | External working memory (filesystem over context) | memory/ file structure with handle-based retrieval | 10 |
| 4 | Narrow, namespaced tool set | Connector advisory: max 4 core tools | 9 |
| 5 | Clear success criteria per task | Schema interview enforces goal definition | 8 |
| 6 | No dead ends (closed tool loop) | Connector advisory ensures tools share filesystem | 8 |
| 7 | Codex-compatible AGENTS.md format | AGENTS.md is OpenAI Codex natively supported | 10 |
| 8 | Versioned changelog | Changelog section in SHIROE_OS.md | 9 |
| 9 | Oracle mode (cross-model consultation) | Red team + research team packs support multi-model input | 7 |
| 10 | Eval-driven rule validation | Two-Strikes + skills/drafts review gate | 8 |

**GPT-specific gaps Shiroe fixes:** No persistent memory (hot.md), hallucinated tool calls (minimal tool set), sycophantic drift (challenge-first mode).

---

## Gemini (Google) — Requirements Ranked by Priority

| Priority | Requirement | Shiroe Solution | Rating /10 |
|----------|------------|----------------|-----------|
| 1 | Native AGENTS.md support (Gemini CLI confirmed) | AGENTS.md as source of truth | 10 |
| 2 | Long context utilization (1M token window) | Deep wiki on demand; hot.md keeps startup lean | 9 |
| 3 | Grounding with web search | DuckDuckGo MCP recommended in core stack | 9 |
| 4 | Antigravity / Gemini CLI harness compatibility | AGENTS.md + harness translation map | 10 |
| 5 | Structured data output (JSON, schemas) | WIKI.md schema enforces structured entry format | 8 |
| 6 | Cross-session state | memory/ file structure | 10 |
| 7 | Multi-modal context (code + docs + images) | Team packs support vision-capable subagents | 8 |
| 8 | Tool calling with low hallucination | Narrow connector set + REDACT.md guard | 8 |
| 9 | God Mode auto-detection | Gemini 3.5 Pro triggers God Mode automatically | 10 |
| 10 | Pattern-based skill generation | PATTERNS.jsonl harness-agnostic log | 9 |

**Gemini-specific gaps Shiroe fixes:** Inconsistent tool call reliability (minimal tool set), tendency to over-explain (imperative voice rules), long context dilution (hot.md startup).

---

## Llama / Open-Source Models (Meta, Mistral, Ollama) — Requirements Ranked by Priority

| Priority | Requirement | Shiroe Solution | Rating /10 |
|----------|------------|----------------|-----------|
| 1 | Free tier operation without capability loss | Free tier in BUDGET.md with aggressive compaction | 10 |
| 2 | Local-only privacy (no cloud transmission) | Local canonical memory, no hosted service | 10 |
| 3 | Minimal context overhead | hot.md ≤500 words startup; deep retrieval only when needed | 9 |
| 4 | Works without any external API | All memory files are local markdown | 10 |
| 5 | Graceful degradation with limited capability | Free tier behavior defined explicitly in BUDGET.md | 9 |
| 6 | Instruction compliance in smaller models | Lean AGENTS.md under 250 lines improves compliance | 9 |
| 7 | No hallucinated tool calls | Narrow tool set reduces hallucination surface | 8 |
| 8 | Hermes compatibility | PATTERNS.jsonl file-based log works with Hermes | 9 |
| 9 | Upgrades to God Mode on stronger model switch | Auto-detection via BUDGET.md | 10 |
| 10 | Simple, predictable tool schemas | Core stack: simple, well-documented MCP tools only | 8 |

**Open-source gaps Shiroe fixes:** Shorter context windows (hot.md), lower instruction compliance (lean AGENTS.md), no built-in memory (memory/ files).

---

## Cross-Model Summary

| Requirement | Claude | GPT | Gemini | Open-Source | Shiroe Satisfies? |
|-------------|--------|-----|--------|-------------|-----------------|
| Lean startup context | Critical | Critical | Critical | Critical | Yes: hot.md + stub CLAUDE.md |
| Persistent cross-session memory | Yes | Yes | Yes | Yes | Yes: memory/ files |
| Privacy-first local memory | Medium | Medium | Medium | Critical | Yes: local canonical, no hosted service |
| Anti-sycophancy modes | Yes | Partial | Partial | Partial | Yes: challenge-first in SHIROE_OS |
| Harness-agnostic format | Yes | Yes | Yes | Yes | Yes: AGENTS.md standard |
| Free tier operation | N/A | N/A | N/A | Critical | Yes: BUDGET.md Free tier |
| Tool set minimalism | Yes | Yes | Yes | Critical | Yes: connector advisory |
| Rule lifecycle management | Yes | Partial | Partial | Partial | Yes: Two-Strikes, skills/drafts/ |
| God Mode auto-detection | N/A | N/A | N/A | N/A | Yes: model-based auto-detection |
| Pattern-based skill generation | Partial | Partial | Partial | Partial | Yes: PATTERNS.jsonl |

---

## Shiroe Ratings by Parameter (Cross-Model Average)

| Parameter | Score /10 | Notes |
|-----------|-----------|-------|
| Harness portability | 9.5 | AGENTS.md standard + translation map. Near-universal. |
| Memory persistence | 10 | File-based, works with any harness, any model. |
| Privacy protection | 9.5 | PRIVACY.md + REDACT.md + SHARING_POLICY.md. Best-in-class. |
| Token efficiency | 9 | hot.md startup + deep retrieval. God Mode for heavy work. |
| Developer experience | 9 | Git-first, conversational setup, skill-draft review. |
| Rule compliance | 8 | 70% community baseline. Shiroe improves via lean file + Two-Strikes. |
| Scalability | 9 | Parent-child wiki rollup handles org-wide knowledge. |
| Free model support | 9.5 | Free tier explicitly designed. Graceful degradation defined. |
| Pattern intelligence | 8.5 | 48-80hr detection window, file-based log. Improves over time. |
| Privacy-aware context sharing | 9.5 | Strongest differentiator vs. comparable systems. |
