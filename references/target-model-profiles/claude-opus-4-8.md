---
target_id: claude-opus-4-8
vendor: anthropic
family: claude
variant: opus-4-8
source_url: https://github.com/asgeirtj/system_prompts_leaks/blob/main/Anthropic/claude-opus-4.8.md
source_updated_at: 2026-06-09
# community mirror repo, not the vendor — see issue #175
source_authority: third_party
last_verified_catalog_sha: 5d3c7696339b4d8add91808e20e3fe3e29a12957
extracted_by: zeref v1.2 profile-extractor (main-thread Opus 4.7)
extracted_at: 2026-07-11

# Cost-router inputs (measured from source; 1 token ~ 4 bytes)
system_prompt_bytes: 183530
system_prompt_tokens: 45000
tool_declaration_tokens: 25000
bare_prompt_tokens: 20000
prompt_cache_ttl_min: 5

# Output-shape defaults (target already enforces — Zeref should NOT re-instruct)
output_style: prose-first-terse-then-elaborate
markdown_default: minimal
emoji_default: no
hedging_default: low
apology_default: minimal
lists_default: no
questions_per_response_max: 1
avoids_words: [genuinely, honestly, actually]

# Tool-use format the target expects — Zeref should MATCH
tool_use_format: xml-function-calls
tool_dispatch: parallel-when-independent
tool_result_frame: tool_result-tagged
tool_reference_convention: '<function_calls>/<invoke>'

# Constraint signature — Zeref should PRE-SHAPE to match
refusal_signature: constitutional
persona_lock: neutral-warm
identity_reference_ok: [claude, anthropic]
copyright_max_words: 15
copyright_max_quotes_per_response: 1
hard_limits:
  - weapons (conventional + CBRN)
  - malicious code
  - CSAM / child safety
  - persuasive content attributed to real public figures

# Caveman-handoff skip list — target already knows; do NOT re-declare
already_knows:
  - available_tools_and_signatures
  - todays_date  # target has web_search + can look up
  - user_platform_generic
  - safety_rules_baseline
  - tool_use_semantics
  - memory_system_semantics
  - artifact_system_semantics
  - copyright_compliance_baseline
  - refusal_style
  - list_vs_prose_defaults

# Prompt-context-engine hints
prefers_structured_task_brief: yes
prefers_success_criteria: yes
prefers_explicit_context_pointer: yes
prefers_short_thinking: n/a  # thinking is a separate channel
prefers_xml_scoped_task_wrapper: yes

# Built-in surfaces available at target
built_in_tools:
  - web_search
  - tool_search
  - find_location
  - tool_knowledge
  - memory (past_chats)
  - artifacts (with persistent_storage)
  - computer_use (Claude Cowork)
  - end_conversation

# Router-cost multipliers (relative to Sonnet 4.6 baseline)
input_cost_multiplier: 5.0
output_cost_multiplier: 5.0
cache_hit_multiplier: 0.1

# Diff hints
notes: |
  Largest Anthropic system prompt in the catalog. Full-tool prompt ~45k
  input tokens BEFORE Zeref's wrapper — prompt caching is non-optional.
  Zeref's caveman-handoff should treat this as the target with the
  broadest already_knows set: safety, tools, memory, artifacts, format
  are all pre-declared. Aggressive skip list expected to yield ~30-40%
  reduction on typical handoffs.

  Fable 5 (personality-tuned sibling) shares tool set and formatting
  defaults; primary diff is persona-lite. Reuse this profile as basis
  for `claude-fable-5.md` with a persona-override note.
---

# claude-opus-4-8 — Zeref target profile

Derived-summary schema — no source text vendored. See
[skills/imported/system-prompts-leaks/README.md](../../skills/imported/system-prompts-leaks/README.md)
for policy.

Consumers:
- `shiroe/prompt/inject.py` — target-aware wrapper
- `shiroe/memory/cost_router.py` — length-aware cost
- `skills/caveman-handoff/SKILL.md` — target-aware skip list
- `skills/prompt-context-engine/SKILL.md` — profile-aware classification
- `_shared/model-resolver.md` — cross-linked row

Freshness: profile refuses at load if `source_updated_at` is >60 days
stale relative to `zeref release check` invocation date.
