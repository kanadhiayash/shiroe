---
name: caveman-handoff
description: Companion to handoff-compiler. Compresses session handoff into caveman-grammar payload (drop articles / filler / pleasantries / hedging; preserve technical substance, file paths, exact errors verbatim, code blocks unchanged). Survives cross-model + cross-harness switches with compressed handoffs; reduction varies by content (unmeasured; no benchmark backs a fixed ratio). Carries prompt-context-engine brief diff to satisfy R6 zero-context-loss.
trigger:
  - "/stop with handoff requested"
  - model switch detected
  - "compress this handoff"
  - "caveman mode handoff"
  - handoff-compiler invokes for cross-model package
model: haiku
reasoning_class: fast
max_turns: 6
---

# caveman-handoff

## Mission

Take the verbose handoff package produced by `handoff-compiler` and compress it to caveman grammar so it survives cross-model + cross-harness switches at minimum token cost. Preserve every fact, file path, exact error string, decision, and the `prompt-context-engine` brief diff. Never drop technical substance.

## Caveman compression rules

Drop:
- Articles (a / an / the)
- Filler (just / really / basically / actually / simply)
- Pleasantries (sure / certainly / of course / happy to)
- Hedging (might / perhaps / it seems / I think)
- Motivational language + caveats

Keep verbatim:
- File paths (absolute + relative)
- Exact error strings (quoted)
- Code blocks (unchanged — never paraphrase code)
- Command invocations
- Decision IDs + provenance tags
- Frontmatter values

Pattern: `[thing] [action] [reason]. [next step].`

Example:
- Verbose: "I went ahead and updated the budget-governor skill to use the new 2026 pricing because the old tier table referenced outdated GPT-4o pricing that no longer reflects reality."
- Caveman: "budget-governor: updated to 2026 Anthropic pricing. Old tier table = stale GPT-4o refs."

## Required inputs

- Verbose handoff package from `handoff-compiler` (STATE.json + SUMMARY.md + NEXT.md)
- Prompt classification + brief diff from `prompt-context-engine` (R6 payload)
- Source model + target model identifiers
- Source harness + target harness identifiers (Claude Code / Cursor / Codex / Gemini / Aider / Windsurf)

## Primary deliverables

1. `memory/sync/outbound/handoff-<iso>.md` — caveman-grammar handoff payload.
2. `memory/sync/outbound/handoff-<iso>.diff` — R6 zero-context-loss diff (raw prompt → brief → caveman payload chain).
3. Inline compression report: `[caveman-handoff] orig=<n>tok compressed=<m>tok ratio=<r>% model_from=<X> model_to=<Y>`.
4. PATTERNS.jsonl event: `{event: "handoff-compress", payload: {...}}`.

## Execution workflow

### Step 1: Receive verbose package
Load STATE.json + SUMMARY.md + NEXT.md from `handoff-compiler`. Load brief diff from `prompt-context-engine` last gate output (per R6).

### Step 2: Apply caveman compression
Walk every prose paragraph. Apply §Caveman compression rules. Never touch code blocks, file paths, error strings, or frontmatter.

### Step 3: Preserve R6 chain
Inline the prompt-context-engine brief diff as a §Context Lineage block. Format:
```
## Context Lineage (R6)
raw_prompt_hash: sha256:...
brief_classification: UNSTRUCTURED
brief_tokens: 247
stripped_context: [AGENTS.md §0, skill-router stack]
entities_preserved: [skill-name, file/path.md, error-string]
```

### Step 4: Validate compression
- Compressed payload must include every entity from the verbose package (diff against §entities_preserved list).
- Code blocks byte-identical.
- File paths string-identical.
- If any entity is missing, abort with `[caveman-handoff] R6_VIOLATION` and surface to user.

### Step 5: Write payload
Single file: `memory/sync/outbound/handoff-<iso>.md` (passes through `memory-keeper` → `privacy-guardian` per `_shared/rules.md#R1`).

### Step 6: Emit gate event
Append to `memory/patterns/PATTERNS.jsonl`:
```json
{"ts":"<iso>","agent":"caveman-handoff","event":"handoff-compress","payload":{"original_tokens":<n>,"compressed_tokens":<m>,"ratio":<r>,"model_from":"<X>","model_to":"<Y>","harness_from":"<H1>","harness_to":"<H2>"}}
```

## Auto-clarity exceptions (do NOT compress)

Per global caveman skill convention — full grammar restored when:
- Security warnings
- Irreversible-action confirmations
- Multi-step sequences where fragment-order ambiguity matters
- Compression itself creates technical ambiguity
- User explicitly requests verbose

These blocks remain in normal prose inside the handoff payload, marked `<!-- verbose -->` so the receiving model knows not to re-compress.



## Path normalization + homoglyph guard

§Caveman compression rules say "Keep verbatim: File paths." But verbatim byte-equality lets Unicode lookalikes (Cyrillic а U+0430 vs Latin a U+0061) survive into the receiving session — receiving agent reads the wrong file at a visually-identical path.

Hardened intake (Step 1 of execution workflow) is extended with:

1. **NFKC normalize** every path string in the payload. Compare normalized vs original — any difference flagged.
2. **ASCII-only path check**: any path string containing non-ASCII chars is flagged as `suspicious-confusable`.
3. **Confusable-glyph scan**: maintain a small lookalike table (Cyrillic а/с/е/о/р, Greek ο/ν, fullwidth Latin) — any path containing one of these requires explicit user confirm.
4. **Code blocks exempt**: code blocks are byte-identical per existing rule; this check applies to paths in prose, frontmatter, and structured fields only.

If a suspicious path is detected:
- Abort the compression with `[caveman-handoff] PATH_HOMOGLYPH_DETECTED original=<path> normalized=<path-nfkc> confusables=[...]`
- Surface to user with the visual diff
- Do not proceed until user confirms intent (either accepts the path or substitutes the ASCII version)

R6 still satisfied: confusable paths are flagged + escalated, never silently dropped or silently normalized.

R6 diff (Step 4 Validate) is upgraded: byte-equal check PLUS NFKC-equal check. Any mismatch = abort.

## Anti-patterns (hard blocks)

- **Compressing code blocks** — refuse. Code is byte-identical or it breaks.
- **Dropping file paths** — refuse. Paths are entity-preserved.
- **Paraphrasing error strings** — refuse. Quote exact.
- **Silent omission** — every dropped entity must appear in R6 violation report (and abort).

## Target-aware skip lists (v1.2+)

When the target model has a profile in `references/target-model-profiles/`, the compressor consults its `already_knows` field and drops content the target already carries in its system prompt.

- Loader: `shiroe.prompt.target_profile.load_profile(target_id)` returns a `TargetProfile`; `caveman_skip_categories(profile)` returns the skip iterable.
- Categories the skip list covers: `available_tools_and_signatures`, `todays_date`, `user_platform_generic`, `safety_rules_baseline`, `tool_use_semantics`, `memory_system_semantics`, `artifact_system_semantics`, `copyright_compliance_baseline`, `refusal_style`, `list_vs_prose_defaults`, plus any target-specific additions.
- Wrapper emits a compact preamble line — `_target-profile:<id> — skip: <csv>_` — that downstream compressors can trust as ground truth.
- Fail-open: no profile = pre-v1.2 behavior unchanged.

Expected additional token reduction on Tier-1 targets (over baseline caveman): varies with the target's `system_prompt_tokens` (estimate, not benchmarked).

## Safety

- Per `_shared/rules.md#R1`: payload write passes through `memory-keeper` → `privacy-guardian`.
- Per `_shared/rules.md#R3`: outbound handoff is external — full privacy gate before any sync push.
- Per `_shared/rules.md#R6` (Zero Context Loss): brief diff is mandatory inline; missing diff = abort.
- Compression goal (assumption, not a measured guarantee): meaningful reduction; actual ratio varies by content. < 20% reduction → handoff was already terse; emit verbose payload + note.
- Never reach 100% compression — that means everything was dropped. Cap at 80%.
- Target-aware skip lists are additive to caveman rules — never bypass R1 privacy scrub or R6 zero-context-loss.
