---
target_id: gpt-5-5-instant
vendor: openai
family: chatgpt
variant: gpt-5-5-instant
source_url: https://github.com/asgeirtj/system_prompts_leaks/blob/main/OpenAI/gpt-5.5-instant.md
source_updated_at: 2026-05-24
# community mirror repo, not the vendor — see issue #175
source_authority: third_party
last_verified_catalog_sha: 5d3c7696339b4d8add91808e20e3fe3e29a12957
extracted_by: shiroe v1.2 profile-extractor (main-thread Opus 4.7)
extracted_at: 2026-07-11

# Cost-router inputs
system_prompt_bytes: 15102
system_prompt_tokens: 3800
tool_declaration_tokens: 2200
bare_prompt_tokens: 1600
prompt_cache_ttl_min: 5

# Output-shape defaults (target already enforces — Shiroe should NOT re-instruct)
output_style: markdown-verbose-answer-first
markdown_default: yes
emoji_default: no
hedging_default: low-penalty-driven
apology_default: low
lists_default: yes
questions_per_response_max: low  # penalty for asking for info already in context
avoids_words: []
built_in_priority_order:
  - answer-user-request-directly
  - apply-user-context
  - never-ask-what-context-answers

# Tool-use format
tool_use_format: json-function-calls
tool_dispatch: sequential
tool_result_frame: assistant-tool-return
tool_reference_convention: 'namespaced tool names (personal_context, file_search, image_gen, web, api_tool)'
tool_input_json_default: yes
freeform_input_marker: FREEFORM

# Constraint signature
refusal_signature: penalty-driven-context-adherence
persona_lock: chatgpt-assistant
identity_reference_ok: [chatgpt, openai, gpt-5-5]
copyright_max_words: not-explicit
hard_limits:
  - inline-json-of-tool-arguments-visible
  - restating-context-questions
  - personal_context-as-file-source

# Caveman-handoff skip list — target already knows
already_knows:
  - available_tools_and_signatures
  - todays_date  # explicit current_date in system prompt
  - knowledge_cutoff  # explicit
  - user_bio_snippet_semantics
  - user_memory_call_conventions
  - file_search_semantics
  - image_gen_semantics
  - citation_format  # inline 【url|anchor|turnN】

# Prompt-context-engine hints
prefers_structured_task_brief: mixed  # answer-first culture but tolerates structured
prefers_success_criteria: no  # target's own priority order overrides
prefers_explicit_context_pointer: yes  # explicit "use user context" mandate
prefers_short_thinking: yes  # instant variant, not thinking

# Built-in surfaces
built_in_tools:
  - personal_context
  - file_search
  - image_gen
  - web
  - api_tool  # slack, gmail, etc — namespaced

# Router-cost multipliers (relative to Sonnet 4.6 baseline)
input_cost_multiplier: 0.4
output_cost_multiplier: 0.5
cache_hit_multiplier: 0.5

# Diff hints
notes: |
  Instant (non-thinking) variant. Small system prompt (~4k tokens vs
  Opus 4.8's 45k) — Shiroe's compression yield here is smaller in
  absolute terms but higher in %-of-budget. Target's penalty-driven
  refusal signature means Shiroe should NEVER re-ask what context
  already answers; caveman-handoff should include an explicit
  context-availability preamble.

  Thinking variant (`gpt-5-5-thinking.md`) differs — extract as
  separate profile in Tier-1 batch. API variant differs on tool
  packaging — separate profile.

  Codex variants (`OpenAI/Codex/gpt-5.5.md`, `.../gpt-5.6.md`) share
  the JSON tool-use format but reshape the priority order for
  code-focused agentic loops — extract as Codex-namespaced profiles.
---

# gpt-5-5-instant — Shiroe target profile

Derived-summary schema — no source text vendored.

Consumers: same as [claude-opus-4-8.md](claude-opus-4-8.md).
