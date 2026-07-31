#!/usr/bin/env bash
# shiroe-publish-releases.sh — create GitHub Releases for all SemVer tags
# Per Phase H6 of v2.6.1 history-reconstruction campaign.
#
# Prerequisites:
#   1. gh CLI installed:           brew install gh
#   2. gh authenticated:           gh auth login
#   3. Tags + main already pushed: git push origin main && git push origin --tags
#
# Usage:
#   cd <repo-root>
#   bash scripts/shiroe-publish-releases.sh         # dry-run (default)
#   bash scripts/shiroe-publish-releases.sh --apply # actually create releases
#
# Idempotent: skips tags that already have a release.

set -e

REPO="kanadhiayash/zeref-os"
NOTION="https://copper-tv-288.notion.site/Zeref-Agent-OS-Command-Center-358d695d836a81af9f6adf30770217c3"
DRY_RUN=true
if [ "${1:-}" = "--apply" ]; then
  DRY_RUN=false
fi

if ! command -v gh >/dev/null 2>&1; then
  echo "ERROR: gh CLI not installed. Run: brew install gh && gh auth login"
  exit 1
fi

if ! gh auth status >/dev/null 2>&1; then
  echo "ERROR: gh not authenticated. Run: gh auth login"
  exit 1
fi

create_release() {
  local tag=$1
  local title=$2
  local body=$3
  local flags=$4

  if gh release view "$tag" -R "$REPO" >/dev/null 2>&1; then
    echo "SKIP $tag — release already exists"
    return 0
  fi

  if [ "$DRY_RUN" = true ]; then
    echo "[DRY-RUN] gh release create $tag $flags --title \"$title\""
    return 0
  fi

  echo "CREATE $tag — $title"
  echo "$body" | gh release create "$tag" \
    -R "$REPO" \
    --title "$title" \
    --notes-file - \
    $flags
}

# ============================================================================
# Pre-rebrand legacy chain (prerelease=true)
# ============================================================================

create_release "v2.0.0" \
  "Zeref OS v2.0.0 — CLAUDE.md + INSTALL.md + registry update (legacy)" \
  "**Zeref OS v2.0.0** (legacy / pre-rebrand)

- Released: 2025 (legacy era)
- Spec ref: AGENTS.md predecessor (Zeref Agent OS v2.x form)
- Command center: $NOTION

## What changed
- CLAUDE.md added
- INSTALL.md added
- Hardened .gitignore
- Registry update
- Validator fix
- Wiki untracked

## Ideology
Zeref Agent OS era. Closer to portability than v1.x but still Claude-locked. Harness coupling limited cross-tool use.

## Status
Legacy (pre-rebrand). Tag restored in v2.6.1 history-reconstruction campaign from existing commit SHA \`4da18af\`. Schema-evolution errors expected against current plugin loader.

## Source
[CHANGELOG-LEGACY.md](../blob/main/CHANGELOG-LEGACY.md)" \
  "--prerelease"

create_release "v2.1.0" \
  "Zeref OS v2.1.0 — fleet consolidation 112→102 skills (legacy)" \
  "**Zeref OS v2.1.0** (legacy / pre-rebrand)

- Released: 2025 (legacy era)
- Command center: $NOTION

## What changed
- Fleet consolidation: 112 → 102 skills

## Ideology
Late Zeref Agent OS era. Started recognizing skill bloat; consolidation was incremental. Full reset came at v4.0.

## Status
Legacy. Tag restored from existing commit SHA \`552dbaf\`.

## Source
[CHANGELOG-LEGACY.md](../blob/main/CHANGELOG-LEGACY.md)" \
  "--prerelease"

create_release "v3.0.0" \
  "Zeref OS v3.0.0 — Context Engine + Agent Harness OS (legacy)" \
  "**Zeref OS v3.0.0** (legacy / pre-rebrand)

- Released: 2025 (legacy era)
- Command center: $NOTION

## What changed
- Zeref Agent OS v3.0.0 — Context Engine + Agent Harness OS framing
- Always-on multi-agent council
- CEO persona

## Ideology shift
Introduced council/CEO framing. Later judged theatrical, single-user, off-mission. v4.0 philosophical reset removed this layer entirely.

## Status
Legacy. Tag restored from existing commit SHA \`b9f4aac\`.

## Source
[CHANGELOG-LEGACY.md](../blob/main/CHANGELOG-LEGACY.md)" \
  "--prerelease"

create_release "v4.0.0" \
  "Zeref OS v4.0.0 — philosophical reset (legacy)" \
  "**Zeref OS v4.0.0** (legacy / pre-rebrand)

- Released: May 2026
- Command center: $NOTION

## What changed (MAJOR ideology shift)
- **Deleted**: 109 specialist skills, 5 agents (fleet-router, council-convener, executive-qa, release-governor, context-engine), 3 identity files (ZEREF.md, ZEREFOS.md, ZEREFPROJECT.md), 14 zeref-prefixed commands, output-styles, registry, 5 v3 helper scripts
- **Built**: 10 disciplined skills, 6 disciplined agents, 7 commands, 5 config files
- Memory/ scaffold with append-only event log + snapshots
- 3 privacy modes (exact/abstract/local-only)
- AGENTS.md canonical spec
- Net diff: −26,690 / +1,949 lines
- Always-on context: 5,035 → 905 tokens (82% reduction)

## Ideology shift
**The shape clicked.** Local-first context + memory engine. Harness-agnostic. Privacy-first. Human arbitration on contradictions. Progressive activation.

## Status
Legacy (pre-rebrand). Tag restored from existing commit SHA \`d551d8a\`. This is the architectural foundation that v1.0.0 (post-rebrand) inherited.

## Source
[CHANGELOG-LEGACY.md](../blob/main/CHANGELOG-LEGACY.md)" \
  "--prerelease"

create_release "v4.1.0" \
  "Zeref OS v4.1.0 — M2 contradiction-resolution + parent-sync (legacy)" \
  "**Zeref OS v4.1.0** (legacy / pre-rebrand)

- Released: May 30, 2026
- Command center: $NOTION

## What changed
- \`contradiction-resolution\` — full impl (was stub in v4.0)
  - Subject/predicate/value fingerprint matching
  - Halt write on conflict → CONFLICTS.md queue → user arbitrates
  - 4 explicit anti-patterns refused
- \`parent-sync\` — full impl (was stub in v4.0)
  - Staged outbound to memory/sync/outbound/<iso>/
  - Per-push approval gate
  - Provenance preserved on rollup
  - Local-only mode blocks all parent sync

## Status
Legacy. Tag restored from existing commit SHA \`0c7925a\`.

## Source
[CHANGELOG-LEGACY.md](../blob/main/CHANGELOG-LEGACY.md)" \
  "--prerelease"

create_release "v4.2.0" \
  "Zeref OS v4.2.0 — M3 pattern-observer + pattern-to-skill (legacy)" \
  "**Zeref OS v4.2.0** (legacy / pre-rebrand)

- Released: May 30, 2026
- Command center: $NOTION

## What changed
- \`pattern-observer\` — full impl
  - 72h rolling window scan of session events
  - Jaccard 3-gram similarity ≥0.8 clustering
  - Top-3 per scan; rest suppressed
- \`pattern-to-skill\` — full impl
  - Draft to skills/_drafts/<name>/
  - Immutable PROVENANCE.md
  - 4 review actions: approve / edit / reject / defer
- v4 roadmap complete — no stubs remain

## Status
Legacy. Tag restored from existing commit SHA \`dcde0e2\`.

## Source
[CHANGELOG-LEGACY.md](../blob/main/CHANGELOG-LEGACY.md)" \
  "--prerelease"

create_release "v4.3.0" \
  "Zeref OS v4.3.0 — v4.x canon import + team packs (legacy)" \
  "**Zeref OS v4.3.0** (legacy / pre-rebrand — last before v1.0.0 rebrand)

- Released: May 31, 2026
- Command center: $NOTION

## What changed
- v4.x canon imported to references/v4x-canon/ (read-only)
- **Memory layout flattened**: memory/wiki/* → flat memory/
- **Root privacy templates**: PRIVACY.md, REDACT.md, SHARING_POLICY.md (default abstract; all connectors OFF)
- **Team packs (6)**: solo / build / research / red / audit / ship via /team [type]
- **Harness stubs**: .cursor/rules/shiroe.mdc, .windsurfrules, .aider.conf.yml.example
- Two-Strikes Rule codified
- Connector Advisory + Harness Translation Map in references/
- Migration script (idempotent, git-mv, pre-migration snapshot)

## Status
Legacy. Tag restored from existing commit SHA \`94ff791\`. Immediate precursor to v1.0.0 canonical release + rebrand.

## Source
[CHANGELOG-LEGACY.md](../blob/main/CHANGELOG-LEGACY.md)" \
  "--prerelease"

# ============================================================================
# Post-rebrand canonical chain (full releases)
# ============================================================================

create_release "v1.0.0" \
  "Zeref OS v1.0.0 — canonical release + rebrand" \
  "**Zeref OS v1.0.0** (post-rebrand canonical)

- Released: May 31, 2026
- Spec ref: AGENTS.md (root)
- Command center: $NOTION

## What changed
Plugin renamed (Zeref Skills Fleet / Agent OS → **Zeref OS**). Version clock reset. Wholesale nomenclature adoption from v4.x canon.

- Flat memory/ layout (no more memory/wiki/)
- Root privacy templates (PRIVACY/REDACT/SHARING_POLICY at repo root)
- Default privacy mode: \`abstract\`
- All connectors OFF by default
- 10 disciplined skills, 6 agents, 8 commands, 6 team packs
- 3 harness stubs (.cursor / .windsurf / .aider)

## Ideology
Years of local iteration converged here. Plugin renamed; version clock reset; project takes final form.

## Migration
v4.3 → v1.0.0 rebrand. No data migration — all memory files keep paths + content.

## Source
[CHANGELOG-LEGACY.md](../blob/main/CHANGELOG-LEGACY.md)" \
  ""

create_release "v2.5.0" \
  "Zeref OS v2.5.0 — Deep Audit Campaign (Phases A-F)" \
  "**Zeref OS v2.5.0** (post-rebrand canonical)

- Released: June 5, 2026
- Spec ref: AGENTS.md
- Command center: $NOTION

## What changed
6-phase deep audit campaign shipped against v2.0 baseline. **Rubric 8.00/10** (from v2.0 7.13).

### Phase A — Claim Inventory + Evidence Grading
- 85-claim audit, 71% VERIFIED, 22% PARTIAL, 7% UNVERIFIED, 0% FALSE

### Phase B — Sandbox Stress Test
- 300 sandbox rows (10 skills × 5 tests × 6 dims)

### Phase C — Security + Vulnerability Hunt
- 8 attacks CVSS-scored. 2 CRITICAL closed (PII regex, email default)

### Phase D — Operational Workarounds (L1-L11)
- L1 PII regex tightened; L2 email enabled; L3 runner.py
- L4 db-status; L5 \`zeref init\`; L6 dogfood
- L7 connector-stub; L8 grep-with-context draft; L9 MemoryLock
- L10 atomic_write; L11 PII scrub before disk

### Phase E — Rubric Re-Scoring
- 8 dims, all cite artifacts. 7.13 → 8.00.

### Phase F — Human UX Polish
- README, QUICKSTART, dashboard, INSTALL, harness stub QA

## Runtime added
\`shiroe/{__init__,__main__,cli,dashboard,db,demo,lock,privacy}.py\`

## Knowledge-OS additions
SOUL.md, pyproject.toml, dashboard.html, _shared/rules.md (R1-R4)

## Migration
None required. Additive only.

## Source
[CHANGELOG.md §2.5.0](../blob/main/CHANGELOG.md#250--2026-06-05)" \
  ""

create_release "v2.6.0" \
  "Zeref OS v2.6.0 — Auto-Gated Execution (4-gate chain)" \
  "**Zeref OS v2.6.0** (post-rebrand canonical)

- Released: June 8, 2026
- Spec ref: AGENTS.md §Auto-Activation Gates + §Model-Tier Routing + Core Principles 13-14
- Command center: $NOTION

## What changed (MAJOR architecture shift)

Zeref shifts from **reactive memory engine** to **proactive auto-gated execution system**. Every major task passes 4 sequential gates before any execution-model token spend:

\`budget classification → skill-stack selection → prompt restructuring → handoff\`

Each gate declares output inline; user can override before execution.

### Skills (+4, count 10 → 14)
- **skill-router** (Gate #2): task domain → smallest-useful-stack (1 lead + 2-3 support + 1 QA)
- **fleet-activator**: live-probes ECC / claude-obsidian / Graphify / browser-harness / notebooklm / gstack
- **prompt-context-engine** (Gate #3): STRUCTURED / SEMI-STRUCTURED / UNSTRUCTURED classifier
- **caveman-handoff**: cross-model handoff compression with R6 preservation

### budget-governor (rewrite, Gate #1)
- 2026 Anthropic pricing (Haiku 4.5 / Sonnet 4.6 / Opus 4.7)
- Cost Weight Classification (CRITICAL / HIGH / MEDIUM / LOW)
- Auto-Activation Rule (6 steps)
- Legacy Free/Standard/God Mode aliases preserved

### AGENTS.md
- Core Principle 13: Cost-Weight Auto-Gate
- Core Principle 14: Task-Weight Model Routing
- ## Auto-Activation Gates section (3 gates)
- ## Model-Tier Routing section (weight → model matrix + cascade)

### _shared/rules.md
- **R6 Zero Context Loss** — every fact/entity/constraint from raw prompt survives restructure/routing/handoff

### Registry
- 10 → 14 entries

## Migration
None required. Additive. Legacy tier aliases preserved for tests/scores-v*.csv back-compat.

## Decision record
[docs/adr/zeref_auto-gated-execution_adr_approved_yk_2026-06-08_v1.0.md](../blob/main/docs/adr/zeref_auto-gated-execution_adr_approved_yk_2026-06-08_v1.0.md)

## Source
[CHANGELOG.md §2.6.0](../blob/main/CHANGELOG.md#260--2026-06-08)" \
  ""

create_release "v2.6.1" \
  "Zeref OS v2.6.1 — Audit + Hardening Campaign (9.88/10 rubric)" \
  "**Zeref OS v2.6.1** (post-rebrand canonical — LATEST)

- Released: June 8, 2026
- Spec ref: AGENTS.md (full) + _shared/rules.md#R6 + _shared/model-resolver.md
- Command center: $NOTION

## What changed

Full v2.5-style deep audit against v2.6.0 surface. **7-phase campaign, 15 L-items shipped.** Every Auto-Activation Gate gained code-backed enforcement. All Phase C CRITICAL + HIGH + MEDIUM closed before push.

### Phases A-G
- **A — Claim Inventory**: 52 claims; 60% VERIFIED; 1 FALSE (validator hardcode L1)
- **B — Sandbox Stress**: 150 rows (5 skills × 5 tests × 6 dims); 76% pass; failures → L9-L12
- **C — Security Hunt**: 8 attacks CVSS-scored
  - 2 CRITICAL (V01 gate-spoof, V02 prompt-injection) — closed via L3 + L10
  - 2 HIGH (V03 probe-spoof, V04 homoglyph) — closed via L9 + L12
  - 2 MEDIUM (V05 silent override, V06 race) — closed via L13 + L11
- **F — Arbitration**: 4 AskUserQuestion batches, 4 decisions logged
- **D — L1-L15 shipped**
- **E — Rubric re-score**: 8.00 → **9.88/10** (+1.88; +23.5%)
- **G — Ship**: wiki-maintenance refresh; validator clean; manual-confirm push

### L-items shipped (15)
- **L1** Validator dynamic skill count from registry (Skills 14/14)
- **L2** Model resolver — full Anthropic ids canonical; \`model_alias\` for back-compat
- **L3** \`lint_patterns_log()\` — PATTERNS.jsonl event allowlist + per-event schema (advisory + lint)
- **L4** R6 sweep — coverage 4 → 9 of 14 SKILL.md Safety sections
- **L5 + L15** Event schema — 11 event types; weight/tier enum; stack-cap lint
- **L9** fleet-activator marker-file probe (closes V03)
- **L10** prompt-context-engine injection filter (closes V02 CRITICAL)
- **L11** prompt-context-engine 60s irreversibility cool-down (closes V06)
- **L12** caveman-handoff NFKC + homoglyph guard (closes V04)
- **L13** budget-governor dual-key override (closes V05)
- **L14** skill-router stack-cap lint (closes V07)

### Memory layer reconciled (C1 memory-drift root cause)
- Retroactive v2.5.0 + v2.6.0 + v2.6.1 logs to memory/DECISIONS.md
- C1-C5 surfaced; C2-C4 marked resolved
- R1-R6 risks logged with mitigation refs

### Validator state
\`\`\`
Skills:           14/14 (from shiroe-registry.json)
Agents:           6/6
Commands:         8/8
Team packs:       6/6
Config:           5/5
Root privacy:     3/3
v4x canon:        6/6
Harness stubs:    3/3
Memory layout:    flat
PATTERNS lint:    0 finding(s)
✔ Validation passed
\`\`\`

### Rubric (8 dims, all cite artifacts)
| Dim | v2.5 | v2.6.1 | Δ |
|---|---|---|---|
| Vision | 9 | 10 | +1 |
| Execution | 7 | 9 | +2 |
| Documentation | 8 | 10 | +2 |
| Architecture | 8 | 10 | +2 |
| Operational Readiness | 8 | 10 | +2 |
| Portfolio Value | 8 | 10 | +2 |
| Investor Credibility | 8 | 10 | +2 |
| Engineer Credibility | 9 | 10 | +1 |

Execution = 9 (not 10) because cascade-replay test deferred to v2.7.

## Out of scope (deferred to v2.7)
- Cross-harness live runs (SHR-B07) — Cursor / Aider / Gemini
- Cascade-replay test (path to 10.00 Execution)
- pipx PyPI publish
- 'Zeref OS' → 'Zeref' rebrand

## Decision record
[docs/adr/zeref_audit-hardening-l1-l15_adr_approved_yk_2026-06-08_v1.0.md](../blob/main/docs/adr/zeref_audit-hardening-l1-l15_adr_approved_yk_2026-06-08_v1.0.md)

## Source
[CHANGELOG.md §2.6.1](../blob/main/CHANGELOG.md#261--2026-06-08)" \
  "--latest"

# ============================================================================
echo ""
if [ "$DRY_RUN" = true ]; then
  echo "[DRY-RUN COMPLETE] Re-run with --apply to create releases:"
  echo "  bash scripts/shiroe-publish-releases.sh --apply"
else
  echo "[APPLY COMPLETE] Verify at: https://github.com/$REPO/releases"
fi
