---
name: budget-governor
description: Auto-gate #1. Classifies task cost weight (CRITICAL / HIGH / MEDIUM / LOW), maps to Anthropic model tier (Haiku 4.5 / Sonnet 4.6 / Opus 4.7), enforces cost-tier match before any major task. Scales output verbosity to active tier. Activates on /start, every major task, model change, and budget warning. Legacy Free / Standard / God Mode labels preserved as aliases.
trigger:
  - "every major task (auto-gate)"
  - "CRITICAL classification detected"
  - /start (always-on: reads BUDGET.md and reports tier every session)
  - "config/BUDGET.md" (file change detected)
  - session approaches warn_at_tokens (mid-session auto-trigger)
  - "budget warning"
  - "token limit approaching"
  - "check tier"
  - "what tier am i on"
  - model change detected (re-resolve tier)
model: haiku
reasoning_class: fast
max_turns: 10
---

# budget-governor

## Mission

Auto-gate #1 of the v2.6 four-gate execution chain. No major task proceeds without a stated cost weight + matched model tier. Surface cost-tier mismatch before tokens are spent. Keep verbosity in line with active tier.

## Tier table (2026 Anthropic pricing — authoritative)

| Tier | Reasoning Class | $/1M input | $/1M output | Zeref behavior | Per-skill cap | Legacy alias |
|---|---|---|---|---|---|---|
| **HAIKU** | `fast` (haiku alias) | $1 | $5 | Aggressive compaction, minimal wiki writes, short `/status` outputs | 4 000 tok | Free |
| **SONNET** | `balanced` (sonnet alias) | $3 | $15 | Normal operation, full wiki writes, standard conflict scans | 8 000 tok | Standard |
| **OPUS** | `deep` (opus alias) | $5 | $25 | Full parent-child sync, deep conflict analysis, pattern retrospectives | 16 000 tok | God Mode |

Notes:
- Thinking tokens billed as output tokens (Anthropic 2026).
- Opus deep-reasoning (~claude-opus-4-8) tokenizer ~+35% vs Sonnet for same English text — flag inflation when pinning deep for cost-sensitive work; balanced remains the cost-sensitive flagship.
- Prompt cache reads = 0.1x input cost. Batch API = 0.5x both.
- Free / Standard / God Mode are accepted aliases for HAIKU / SONNET / OPUS (maps to fast/balanced/deep).

User can override tier in `config/BUDGET.md` `model_tier:` field.

## Cost Weight Classification

Every major task is classified before execution. Classification drives model + effort selection.

| Weight | Signals | Typical cost range (per task) | Default model + effort |
|---|---|---|---|
| **CRITICAL** | Multi-skill orchestration, irreversible writes, security-sensitive payloads, architecture decisions, parent-sync exports | $0.50 – $5.00 | Opus 4.7 high (or Opus 4.6 for cost-sensitive flagship) |
| **HIGH** | Cross-file refactor, new skill draft, contradiction arbitration, eval harness run, schema migration | $0.10 – $0.50 | Sonnet 4.6 medium |
| **MEDIUM** | Single-file edit, wiki consolidation, evidence grading on 5–20 claims, README polish | $0.02 – $0.10 | Sonnet 4.6 low / Haiku 4.5 medium |
| **LOW** | Single-fact lookup, formatting fix, single-claim grade, status read | < $0.02 | Haiku 4.5 low |

Signal precedence: highest matching signal wins. If unsure, escalate one tier (never silently downgrade).

## Auto-Activation Rule

Runs before every major task. 6 steps:

1. **Receive task surface** (raw prompt or skill invocation) before any model call.
2. **Classify weight** using §Cost Weight Classification signals. State weight inline.
3. **Resolve active model** from harness env. Map to tier per §Tier table.
4. **Match check**: weight ↔ model.
   - LOW on Opus → flag mismatch ("LOW task on Opus — propose Haiku?"). Block until user confirms or downgrades.
   - CRITICAL on Haiku → hard block. Refuse execution until escalated.
   - HIGH on Haiku, MEDIUM on Opus → warn but allow.
5. **Declare gate result inline**: `[budget-governor] weight=HIGH tier=SONNET match=OK budget_remaining=$3.42`.
6. **Log gate event** to `memory/patterns/PATTERNS.jsonl` (`event: "budget-gate"`, payload includes weight + tier + match + estimated cost).

CRITICAL or HIGH cannot proceed without an explicit stated tier in the gate output. Per AGENTS.md Core Principle 13.

## Operations

### ON /start
1. Read `config/BUDGET.md`
2. Detect active model from harness env; resolve to tier
3. Report active tier + always-on context size
4. Warn if always-on > target (default 2000 tok)

### MID-SESSION
1. Track cumulative tokens via session events
2. At `warn_at_tokens`: surface to user, offer consolidation via `wiki-maintenance`
3. At `hard_cap_tokens`: block writes, force `/done` or summarization

### TIER CHANGE
1. Reload verbosity rules
2. Suggest re-reading `memory/index.md` with new boundary policy
3. Log tier change as event in `memory/patterns/PATTERNS.jsonl`

## Auto-detection rules (model → tier)

| Detected model | Mapped tier | Legacy alias |
|---|---|---|
| `claude-opus-4-*`, `claude-opus-3-*` | OPUS | God Mode |
| `claude-sonnet-4-*`, `claude-sonnet-3-*` | SONNET | Standard |
| `claude-haiku-4-*`, `claude-haiku-3-*` | HAIKU | Free |
| `gpt-4o`, `gemini-3.5-pro` (non-Anthropic high-tier) | OPUS-equivalent | God Mode |
| `gpt-4o-mini`, `gemini-flash-3.5` | SONNET-equivalent | Standard |
| `mistral-*`, `ollama/*`, `gemini-flash` (older) | HAIKU-equivalent | Free |
| unknown | SONNET (safe default) | Standard |

User can override in `config/BUDGET.md` `model_tier:` frontmatter field.



## Dual-key override

User may attempt to override a hard-block (e.g. CRITICAL on Haiku). Single-key override (user types "proceed") is insufficient — Core Principle 14 violation slips through silently.

**Dual-key override contract**:

1. **Key 1**: explicit user-typed override directive containing both the weight + tier + reason:
   `OVERRIDE: CRITICAL on HAIKU — reason=<text>`
2. **Key 2**: `prompt-context-engine` brief diff must include an `<override-acknowledged>` block explicitly naming the tradeoff:
   ```
   <override-acknowledged>
     accepting CRITICAL work on HAIKU tier despite Core Principle 14 hard-block.
     known tradeoffs: lower output quality, less context, no thinking-tokens.
     reason: <user-provided text>
   </override-acknowledged>
   ```
3. **Log** override event to `memory/patterns/PATTERNS.jsonl`:
   `event: budget-gate, payload: {weight: CRITICAL, tier: HAIKU, match: OVERRIDE, override_reason: "<text>"}`
4. **pattern-observer** surveils for repeat overrides in 48-80h window — ≥3 same-class overrides triggers `pattern-to-skill` candidate "user routinely overrides X on Y tier — consider reclassifying."

Override events count toward `budget-warn_at_tokens` but bypass the hard-block. Validator (`scripts/zeref-validate.py`) recognizes `match=OVERRIDE` per the `budget-gate` event schema allowlist.

Single-key shortcuts (user just says "override") are rejected with a re-prompt requiring full directive + brief acknowledgement.

## Safety

- Never silently truncate user content
- Always offer consolidation rather than auto-delete
- Per D9 (`_shared/rules.md#R2`): archive consolidated content, never delete
- Gate output is mandatory — no major task proceeds without an inline `[budget-governor]` line
- Per `_shared/rules.md#R6` (Zero Context Loss): cost weight classification must reflect every signal present in the prompt (file count, irreversibility, security-sensitivity) — no signal silently downgraded.
- Cost estimates are floors not ceilings; flag if actual run exceeds estimate by >2x
