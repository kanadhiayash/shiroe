# references/target-model-profiles/ — Zeref target-aware routing hints

One YAML profile per target model that Zeref emits into. Derived summaries
of leaked system prompts from `github.com/asgeirtj/system_prompts_leaks`.
**No source text vendored.**

## Purpose

Zeref's `caveman-handoff`, `prompt-context-engine`, and `cost_router` consume
these profiles to (a) drop content the target already has in its system
prompt and (b) pre-shape prompts to match the target's format and refusal
signatures.

## Schema (canonical fields)

Every profile MUST carry:

- `target_id` — matches `_shared/model-resolver.md` model_id.
- `vendor`, `family`, `variant`.
- `source_url`, `source_updated_at`, `source_authority`, `last_verified_catalog_sha`.
- `source_authority` — one of `official` (published directly by the vendor),
  `third_party` (a mirror/leak repo, no authoritative publisher — e.g. the
  `system_prompts_leaks` catalog these Tier-1 profiles are sourced from), or
  `derived` (reconstructed/inferred, not a direct capture). Grades how the
  freshness ceiling is enforced — see "Freshness policy" below.
- `extracted_by`, `extracted_at`.
- Cost-router: `system_prompt_bytes`, `system_prompt_tokens`,
  `tool_declaration_tokens`, `bare_prompt_tokens`, `prompt_cache_ttl_min`.
- Output-shape: `output_style`, `markdown_default`, `emoji_default`,
  `hedging_default`, `apology_default`, `lists_default`.
- Tool-use: `tool_use_format`, `tool_dispatch`, `tool_result_frame`.
- Constraints: `refusal_signature`, `persona_lock`, `identity_reference_ok`,
  `hard_limits[]`.
- Compression: `already_knows[]` — what target's system prompt covers so
  Zeref's wrapper drops it.
- Prompt-context-engine hints: `prefers_structured_task_brief`,
  `prefers_success_criteria`, `prefers_explicit_context_pointer`.
- Built-ins: `built_in_tools[]`.
- Router cost: `input_cost_multiplier`, `output_cost_multiplier`,
  `cache_hit_multiplier` (relative to Sonnet 4.6 baseline = 1.0).

## Tier-1 catalog (v1.2 target — 12 profiles)

| # | target_id | status |
|---|---|---|
| 1 | claude-opus-4-8 | shipped (canary) |
| 2 | gpt-5-5-instant | shipped (canary) |
| 3 | claude-sonnet-5 | pending |
| 4 | claude-code | pending |
| 5 | gpt-5-5-thinking | pending |
| 6 | gpt-5-6-sol-extra-high | pending |
| 7 | gemini-3-5-flash | pending |
| 8 | gemini-3-1-pro | pending |
| 9 | grok-4-2 | pending |
| 10 | grok-expert | pending |
| 11 | codex-gpt-5-5 | pending |
| 12 | cursor | pending |

## Freshness policy

- Profiles carry `source_updated_at` from the catalog.
- `zeref release check` and `zeref doctor` refuse PASS (hard-fail) when a
  profile with `source_authority: official` is >60 days stale relative to
  the release date — an official publisher exists to re-verify against, so
  staleness there is treated as unverified drift.
- A `third_party`/`derived` profile that is >60 days stale downgrades to a
  non-blocking WARNING instead of a hard fail: there is no authoritative
  publisher to re-check it against either way, so refusing to release would
  just be recording a verification nobody could have performed. The
  WARNING still surfaces in the release report and in `zeref doctor` output
  — it is never silently dropped or reported as PASS. (issue #175)
- Monthly refresh cadence (see
  [skills/imported/system-prompts-leaks/README.md](../../skills/imported/system-prompts-leaks/README.md)).

## How to add a profile

1. Fetch source via `gh api repos/asgeirtj/system_prompts_leaks/contents/<path>`.
2. Grep for structural markers: tags, tool declarations, format rules,
   refusal patterns, persona locks.
3. Fill the schema fields — every field mandatory unless documented n/a.
4. Cite `last_verified_catalog_sha` (see
   `gh api repos/asgeirtj/system_prompts_leaks/commits/main -q '.sha'`).
5. Commit under `references/target-model-profiles/<target_id>.md`.
6. Re-run `python3 scripts/zeref-validate.py` (validator will lint schema
   once extended in R7 follow-on).

## Non-negotiables

- No original prompt text in profiles.
- Every observation cited by structural marker (tag names, tool names,
  literal formatting words like "penalty", "critical", "must").
- Profile refuses to load if required fields missing.
- Additional targets (Tier-2, Tier-3) are additive — never break Tier-1
  callers.
