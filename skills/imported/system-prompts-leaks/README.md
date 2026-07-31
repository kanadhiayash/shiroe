---
pack: system-prompts-leaks
mode: reference-only
classification: public
source_url: https://github.com/asgeirtj/system_prompts_leaks
source_default_branch: main
license: research-aggregation (see upstream repo for individual attributions)
outbound_write: forbidden
foreign_code_containment: pass
imported_at: 2026-07-11
imported_by: v1.2 prompt-leaks integration
refresh_cadence: monthly
---

# system-prompts-leaks — reference-only import

## Origin

`github.com/asgeirtj/system_prompts_leaks` — 55k-star catalog of leaked system prompts from Anthropic, OpenAI, Google, Microsoft, xAI, Cursor, Perplexity, Meta, Notion, Mistral, Qwen, and misc AI products (Devin, Hermes, Kagi, Amp, Zed, Docker Gordon, and more). Updated regularly by the maintainer + PR contributors.

## Why Zeref cares

Every prompt Zeref emits lands **after** a target model's own system prompt — which the target has already ingested and cached. If Zeref knows what the target already knows, the `caveman-handoff` + `prompt-context-engine` skills can drop redundant content (tool declarations, format instructions, refusal patterns, persona shifts, constraint restatements) and reclaim 20-40% of the prompt budget for actual task content.

The reverse is equally load-bearing: knowing each target's refusal signature and format quirks lets Zeref pre-shape prompts to match the target's attention biases, avoiding re-prompts and one-shotting more requests.

## Boundary

- **No source text vendored.** Zeref imports **derived observations** only, into `references/target-model-profiles/<target_id>.md` — one 200-400 token YAML per target.
- Original prompts remain the model vendors' IP. Zeref stores summaries + tokens counts + format quirks + refusal signatures, not text.
- Every profile cites `source_url` + `source_updated_at` + `last_verified_sha` from the catalog repo. Freshness is a release-gate subcheck (`shiroe/release/checks.py`).
- `benchmarks/foreign_code_containment.py` trivially green — nothing copied.

## Allowed use

- `gh api repos/asgeirtj/system_prompts_leaks/contents/...` — read-only extraction during Phase 14.
- Reading the catalog interactively during profile-refresh cadence (monthly).
- Citing the catalog URL in `docs/BENCHMARK_REPORT.md` when publishing the token-reduction number.

## Forbidden

- Copying prompt bodies into this repo, `memory/`, `docs/`, or any Zeref-canonical surface.
- Dynamic runtime fetch — profiles are frozen at build time.
- Public claim of specific model behavior derived from leaks beyond what a profile row states.
- Using the leaks catalog as an oracle for legal, safety, or policy claims about any vendor. Zeref treats every profile row as a routing hint, not a fact about the vendor.

## Refresh workflow

1. Monthly, or on any Zeref target-router change.
2. Re-run Phase 14 extraction pipeline (`scripts/refresh-target-profiles.py` — to be added).
3. Diff each profile against its prior version; council-review deltas > 20% on Tier-1 targets.
4. Re-run `benchmarks/token_efficiency.py --target-aware` to confirm reduction floor still holds.
5. Update `references/target-model-profiles/README.md` freshness table.

## Council pack membership

Previously registered in a persona pack that was retired in 2.0.0-alpha.1; now tracked as an external capability reference only (primary evidence surface for token-routing decisions in v1.2+). Not activated by default.
