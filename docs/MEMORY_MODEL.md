# Memory Model

Shiroe stores project memory locally. Human-readable Markdown remains visible in
`memory/`, while structured memory cards live in `memory/state/zeref.sqlite`.

## Memory Cards

Guarded writes use a canonical card with:

- `id`, `type`, `title`, `claim`, `status`
- `confidence`, `evidence_grade`, `source_refs`, `privacy_class`
- `created_at`, `updated_at`, optional validity dates
- `supersedes`, `superseded_by`, `tags`, `owner`

Facts and decisions require `source_refs`. `unknown` and `assumption` cards may
omit sources, but must still carry privacy and evidence metadata.

## Allowed Values

- Types: `fact`, `decision`, `preference`, `constraint`, `risk`, `unknown`,
  `assumption`, `task`, `source_claim`, `contradiction`, `route_policy`,
  `privacy_rule`, `handoff`
- Status: `active`, `superseded`, `disputed`, `archived`, `rejected`, `pending`
- Confidence: `low`, `medium`, `high`, `unknown`
- Evidence grade: `A`, `B`, `C`, `D`, `F`
- Privacy class: `public`, `internal`, `sensitive`, `secret`, `do_not_store`
