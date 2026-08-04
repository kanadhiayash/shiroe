# GitHub Surface Inventory — Wave 1 / PR 01 (SHR-028, SHR-030)

- Recorded at commit: a4549e06d3a4b398fb2476039026eda49501176a
- Recorded at (UTC): 2026-08-04T00:24:02Z
- Access mode: read-only. No GitHub mutation was performed. Every `gh` command below was a GET-equivalent (`repo view`, `issue list`/`view`, `release list`, `gh api ... --jq` on GET endpoints). No `-X POST/PATCH/PUT/DELETE`, no push, no tag, no settings change was issued.

## 1. Git object and ref inventory (SHR-028)

| Metric | Value |
|---|---|
| `git log --oneline \| wc -l` (current branch, `audit/shr-baseline-evidence`) | 143 |
| `git log --all --oneline \| wc -l` | 235 |
| Tags (`git tag --sort=-version:refname`) | `v2.0.0-alpha.1`, `v1.1.1`, `v1.1.0` |
| Local branches | `audit/shr-baseline-evidence` (current), `chore/shiroe__deep-migration`, `chore/shiroe__identity-manifest`, `chore/shiroe__readme-assets`, `claude/zeref-v3-hardening-execution-837d8f`, `dev`, `docs/shiroe__brand-assets`, `docs/shiroe__brand-surfaces`, `docs/shiroe__readme-rewrite`, `docs/shiroe__v3-changelog`, `fix/shiroe__gate-tightening`, `fix/shiroe__retrieval-bm25`, `fix/shiroe__stale-db-path-strings`, `refactor/shiroe__namespace-rename`, `release/shiroe__v3.0.0-alpha.1`, `verify-dev`, `verify-final` |
| Remote-tracking refs | `remotes/origin/HEAD -> origin/main`, `remotes/origin/main` (only `main` is fetched into this worktree's remote-tracking set — the local branches above are local-only, not mirrors of `origin/*`) |

`git count-objects -v`:

```
count: 1034
size: 13392
in-pack: 4842
packs: 3
size-pack: 5532
prune-packable: 673
garbage: 1
size-garbage: 0
```

Note: the command also emitted `warning: garbage found: <home>/Desktop/ZEREF/zeref/.git/worktrees/shiroe-wave-1-pr-1-7e7713/refs`. This is a warning about a stray path under this linked worktree's private git dir (`.git/worktrees/<name>/refs`), not about the object store itself — `garbage: 1 / size-garbage: 0` in the object count above is a zero-byte garbage object, immaterial.

`git log --all --format='%an <%ae>' | sort -u` — all author identities present in history:

```
Yash Kanadhia <235186026+kanadhiayash@users.noreply.github.com>
Yash Kanadhia <kanadhiay@gmail.com>
dependabot[bot] <49699333+dependabot[bot]@users.noreply.github.com>
kanadhiayash <kanadhiay@gmail.com>
```

Four distinct identities, two underlying people/bots: the human author appears under three name/email combinations (a GitHub noreply alias and a personal Gmail address, under two different display names — `Yash Kanadhia` and `kanadhiayash`), plus one bot (`dependabot[bot]`). No third-party human contributors are present in history.

## 2. Legacy identity in history

`git log --all --format='%H %ad %an %s' --date=short | grep -i -E 'zeref|zrf'` — **true total: 91 commits** (confirmed by direct count, matching the ~91 lead). 25 most recent shown; full 91-row list was captured but is truncated here per spec.

| # | SHA | Date | Author | Subject |
|---|---|---|---|---|
| 1 | c25d993b | 2026-07-31 | Yash Kanadhia | chore(shiroe): finish the migration into runtime paths, drop the Zeref hero art (#204) |
| 2 | 523445f4 | 2026-07-31 | kanadhiayash | chore(shiroe): finish the migration into runtime paths, drop the Zeref hero art |
| 3 | 7489de0d | 2026-07-31 | Yash Kanadhia | refactor(shiroe)!: rename the zeref namespace to shiroe (#200) |
| 4 | af604513 | 2026-07-31 | kanadhiayash | refactor(shiroe)!: rename the zeref namespace to shiroe |
| 5 | 0a38c070 | 2026-07-28 | Yash Kanadhia | feat(zeref): runtime hardening program — routing, tokens, context, retrieval, release truth (#176) |
| 6 | dedd02e3 | 2026-07-21 | Yash Kanadhia | docs(zeref): rewrite public documentation for current state (#159) |
| 7 | 6ff43a68 | 2026-07-20 | Yash Kanadhia | Merge pull request #147 from kanadhiayash/chore/zeref__reconcile-main-into-dev |
| 8 | 315b3973 | 2026-07-20 | Yash Kanadhia | Consolidate CI into a single ZRF Verify workflow (#145) |
| 9 | 36848909 | 2026-07-13 | Yash Kanadhia | release: Zeref 2.0.0-alpha.1 — vNext pivot (dev + main folded) (#118) |
| 10 | 028a6633 | 2026-07-13 | Yash Kanadhia | feat(zeref-core): vNext PR 1 — architecture reset + reasoning classes + provider adapters (#97) |
| 11 | c2d17180 | 2026-07-11 | Yash Kanadhia | release(zeref): v1.1.1 — CI green-up (#96) |
| 12 | 2f0b144d | 2026-07-11 | Yash Kanadhia | fix(zeref): semver comparison in check-version-consistency (#94) |
| 13 | 93a2ebaa | 2026-07-11 | Yash Kanadhia | fix(zeref): v1.1.1 — CI green-up + branch cleanup (#93) |
| 14 | 23f3824e | 2026-07-11 | Yash Kanadhia | release(zeref): v1.1.0 audit remediation + v1.2 canary (target profiles) (#90) |
| 15 | 74aef014 | 2026-07-10 | Yash Kanadhia | release(zeref): promote 64-repo lineage upgrade |
| 16 | 15f59b47 | 2026-07-09 | Yash Kanadhia | Merge pull request #52 from kanadhiayash/ci/zeref__dev-main-workflows |
| 17 | cc8419aa | 2026-07-09 | Yash Kanadhia | Merge pull request #50 from kanadhiayash/fix/zeref__green-ci-baseline |
| 18 | b4e6b877 | 2026-07-09 | Yash Kanadhia | Merge pull request #49 from kanadhiayash/fix/zeref__green-ci-baseline |
| 19 | f9700597 | 2026-07-09 | Yash Kanadhia | Merge pull request #48 from kanadhiayash/docs/zeref__public-surface-overhaul |
| 20 | 58ab673d | 2026-07-09 | kanadhiayash | docs(zeref): enhance README with comprehensive project overview and structured sections |
| 21 | ca94b61f | 2026-07-09 | kanadhiayash | "docs(zeref): overhaul public surface and harden repo governance" |
| 22 | 74839c77 | 2026-07-09 | kanadhiayash | test(zeref): refresh benchmark reports after public overhaul |
| 23 | 229800fc | 2026-07-09 | kanadhiayash | docs(zeref): add public surface and release hardening policies |
| 24 | bfad7a28 | 2026-07-09 | kanadhiayash | docs(zeref): archive legacy public surface notes |
| 25 | d40889f4 | 2026-07-09 | Yash Kanadhia | Merge pull request #46 from kanadhiayash/feat/zeref__benchmark-suite |

Remaining 66 commits (#26–#91, oldest is `c8205f2c` on 2026-05-12) run the same pattern back through the repo's full lifecycle: `feat/zeref__*` and `fix/zeref__*` branch merges, `chore(zeref)`/`docs(zeref)` commits from the v2.5–v2.6.1 era, and the earliest commits carrying `Zeref Agent OS` / `zeref-agent-os` naming (SHAs `1bc3d4d9`, `5e9fc677`, `f65fd73b`, `10a29eaa`, `852f5f00`, `c8205f2c`). Full 91-row list is captured in the scan output referenced above; the two most recent (rows 1–4) are the Shiroe rename itself (#200, #204), i.e. the rename commits are themselves indexed by this grep because their subject lines still say "Zeref"/"zeref" while describing the rename away from it.

## 3. Sensitive-string history scan

**Method used:** `git grep -I -i -n -e 'notion.site' -e 'notion.so' -e 'AKIA' -e 'BEGIN RSA' -e 'BEGIN OPENSSH' -e 'ghp_' -e 'sk-' $(git rev-list --all) --` — i.e. the full "grep every commit's tree" method from the task spec (not the `-S`/pickaxe fallback; the direct method completed in well under the time budget on this repo's size, ~235 commits / ~5.5MB packed).

**Coverage limits, stated honestly:**
- This greps the *tree contents at every commit reachable from every ref* (`--all`), which covers every ref currently in `git branch -a`/`git tag` plus their full ancestry. It does **not** cover unreachable/dangling objects (e.g. commits from force-pushes or amends that were never merged and have since been GC'd or are just unreferenced) — those aren't visited by `rev-list --all`.
- It is a plain substring/regex grep over decompressed blob text at each commit snapshot, not a diff-only scan — so a string present in 91 commits' worth of unchanged file history is counted 91 times, not once. Counts below are match-line counts, not "how many times the secret was introduced."
- `git grep` skips binary blobs by content-sniffing (`-I`); base64-embedded data inside a text file (e.g. an SVG with an embedded PNG) is still text-typed and therefore searched, and produced false-positive substring hits (see below).
- No entropy/regex-strength secret scanner (e.g. gitleaks/trufflehog) was run; this is a literal substring scan for the 7 patterns the task specified only.

**Raw hit counts (match-lines across all reachable commit trees):** `notion.site` 1265, `notion.so` 0, `AKIA` 2440, `BEGIN RSA` 186, `BEGIN OPENSSH` 0, `ghp_` 1379, `sk-` 4375.

**Manual triage of the raw hits** (sampled and cross-checked against file paths):

| Pattern | What the hits actually are | Classification |
|---|---|---|
| `notion.site` | Real private Notion URL (`<redacted-notion-host>/...`), appearing across 14 distinct file paths over history (see below) | current-tree cleanup (4 files) + all-history question deferred to PR 07 |
| `AKIA` | Zero real AWS keys. All ~2440 hits are: (a) the literal pattern documented in `CHANGELOG.md` (`` `AKIA…` (AWS access key IDs) ``) and the redaction regex in `.github/workflows/shr-verify.yml`/`privacy-audit.yml`; (b) `shiroe/privacy.py` comments and `tests/test_privacy_redaction.py` fixtures that deliberately construct fake AWS-shaped strings (e.g. `_AKIA = "A" + "KIA"`, `AKIA}IOSFODNN7EXAMPLE`) to test the redaction pipeline; (c) base64-encoded image payload bytes inside `assets/*.svg` that happen to contain the 4-char substring `AKIA` | preserved historical lineage — no real key found |
| `BEGIN RSA` | 100% `tests/test_privacy_redaction.py:52`, a fixture literal `"-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQEA\n-----END RSA PRIVATE KEY-----"` used to test PEM redaction, repeated across ~20+ commits that touched that test file | preserved historical lineage — test fixture, not a real key |
| `ghp_` | 100% test fixtures / docs: `tests/test_privacy_guard.py` (`ghp_AbCdEfGhIjKlMnOpQrStUvWxYz0123`), `tests/test_write_decision.py`, `shiroe/privacy.py` comments, `CHANGELOG.md` pattern documentation | preserved historical lineage — no real token found |
| `sk-` | Overwhelmingly false-positive substring matches (`task-`, `risk-`, `desk-`, `disk-`, etc.) plus deliberate test fixtures (`tests/test_vnext_pr2_storage.py`: `sk-live-1234567890abcdef`; `tests/test_privacy_scan_scope.py`: `"sk-" + "proj-" + ("A"*24)`; `tests/test_anthropic_provider_live.py`: `sk-ant-test-sentinel`) and the redaction regex source in `benchmarks/external/providers/anthropic.py` | preserved historical lineage — no real key found |
| `notion.so` / `BEGIN OPENSSH` | Zero hits, either pattern, any commit | n/a |

**Notion URL detail.** Files that carried `<redacted-notion-host>/...` at some point in history: `.claude-plugin/plugin.json`, `CHANGELOG.md`, `GITHUB_OS.md`, `README.md`, `docs/RELEASE_LOG.md`, `docs/wiki/Home.md`, `docs/wiki/Installation.md`, `docs/wiki/README.md`, `docs/wiki/_Sidebar.md`, `references/v4x-canon/RESEARCH_RESOURCES.md`, `scripts/shiroe-publish-releases.sh`, `scripts/zeref-publish-releases.sh`, `wiki/projects/zeref-v2-rebuild.md`, `wiki/sources/zeref-reference-links.md`.

Cross-checked against the current working tree (see §current-tree grep below): only **4 of those 14 files still exist and still contain the URL today** — `CHANGELOG.md`, `GITHUB_OS.md`, `references/v4x-canon/RESEARCH_RESOURCES.md`, `scripts/shiroe-publish-releases.sh`. This exactly matches the lead given in the task brief. The other 10 paths (`docs/RELEASE_LOG.md`, `docs/wiki/README.md`, `wiki/projects/zeref-v2-rebuild.md`, `wiki/sources/zeref-reference-links.md`, `scripts/zeref-publish-releases.sh`) either no longer exist in the current tree, or (`README.md`, `docs/wiki/Home.md`, `docs/wiki/Installation.md`, `docs/wiki/_Sidebar.md`, `.claude-plugin/plugin.json`) still exist but no longer contain the URL — i.e. it was already removed from those files by a prior commit, but the URL string itself remains permanently readable in the object history of every commit that ever contained it.

**Current-tree private references** (`git grep -n -i -e 'notion.site' -e 'notion.so' -e '/Users/' -e 'icloud'`, HEAD only):

```
CHANGELOG.md:539:      Notion: <redacted:private-notion-url>
GITHUB_OS.md:74:       Notion: <redacted:private-notion-url>
REDACT.md:30:          - absolute_filesystem_paths  # /Users/<name>/..., /home/<name>/...
REDACT.md:70:          | internal_paths | abstract to repo-relative — `/Users/x/proj/foo` → `<repo>/foo` |
references/v4x-canon/RESEARCH_RESOURCES.md:56: - <redacted:private-notion-url>
scripts/shiroe-publish-releases.sh:20:  NOTION="<redacted:private-notion-url>"
skills/privacy-abstraction/SKILL.md:30:        | internal_paths | abstract to repo-relative → `/Users/x/proj/foo` → `<repo>/foo` |
tests/test_benchmark_suite.py:96:     assert "/Users/" not in text and "/home/" not in text, (
tests/test_privacy_guard.py:52:      doc.write_text("Internal path /Users/example/project and email user@example.com", encoding="utf-8")
tests/test_privacy_guard.py:57:      assert "/Users/example/project" not in cleaned
```

The `REDACT.md`, `skills/privacy-abstraction/SKILL.md`, and `tests/test_*` hits for `/Users/` are all self-referential documentation/tests of the redaction system itself (they *describe or test* the `/Users/` pattern, they don't leak one). No `icloud` hits in the current tree (the iCloud reference is confined to GitHub Issue #152, see §5). The two remaining `notion.site` current-tree hits (`CHANGELOG.md`, `GITHUB_OS.md`) plus `references/v4x-canon/RESEARCH_RESOURCES.md` and `scripts/shiroe-publish-releases.sh` are the live, real private URL — see §7 for the deferred-approval item; no rewrite performed here, per scope (PR 07 owns that decision).

## 4. Repository metadata (SHR-030)

`gh repo view kanadhiayash/shiroe --json name,description,visibility,homepageUrl,repositoryTopics,isArchived,hasWikiEnabled,hasIssuesEnabled,defaultBranchRef,licenseInfo,pushedAt`:

| Field | Value |
|---|---|
| name | `shiroe` |
| description | "Local-first AI work control plane for governed execution, model routing, project memory, evidence, handoffs, and team synchronization." |
| visibility | `PUBLIC` |
| homepageUrl | `https://github.com/kanadhiayash/zeref-memory-engine/wiki` |
| isArchived | `false` |
| hasWikiEnabled | `true` |
| hasIssuesEnabled | `true` |
| defaultBranchRef | `main` |
| licenseInfo | MIT License (`mit`) |
| pushedAt | `2026-08-01T05:51:21Z` |
| repositoryTopics | `agent-governance`, `ai-agents-automation`, `ai-agents-framework`, `ai-agents-memory`, `ai-agents-security`, `ai-governance`, `context-management`, `context-management-system`, `developer-tools`, `evidence`, `handoff`, `human-in-the-loop`, `llms`, `local-first-ai`, `model-routing`, `multi-agent`, `policy-engine`, `team-sync`, `work-graph` |

**Lead 1 confirmed:** `homepageUrl` points at `https://github.com/kanadhiayash/zeref-memory-engine/wiki` — the legacy pre-rename repo's wiki, not `shiroe`'s own wiki (which is enabled — `hasWikiEnabled: true` — but unused as the homepage target).

**Lead 2 confirmed:** topics include both `work-graph` and `team-sync`. Cross-checked against `README.md:335-348` ("Limitations" section):
- `README.md:346`: **"No work graphs. No work-graph module exists. Execution, routing, and handoffs are governed independently; nothing yet models them as a graph."** — directly contradicts the `work-graph` topic.
- `README.md:345`: **"Single-machine memory. No shared multi-device story yet, despite the 'every device' framing in the tagline..."** — adjacent to, but not a verbatim match for, `team-sync`; there is no line in README.md that says "team-sync" or "team sync" explicitly (`grep -n -i 'team.sync'` on README.md returns nothing). The `team-sync` topic is unsupported by the same limitation (no multi-device/team story exists), but the task brief's claim that README.md:345-346 "says [team-sync is] unsupported" is only partially literal — 346 covers `work-graph` precisely, 345 covers the underlying capability gap `team-sync` implies, without naming it.

## 5. Issues

`gh issue list --repo kanadhiayash/shiroe --state all --limit 200 --json number,title,state,labels,createdAt`:

- **Total: 73** issues (well under the 200 limit, so this is the complete set).
- **Open: 16, Closed: 57.**

**Issues with legacy identity (`zeref`/`zrf`) in title or labels — 15 of 73:**

| # | State | Title | Labels (legacy-relevant excerpt) |
|---|---|---|---|
| 208 | OPEN | Rename the v1 legacy store path, or document why it keeps the zeref name | `type:refactor` |
| 196 | OPEN | Retrieval: zeref recall trails a plain BM25 ranker on conversational benchmarks | `area:memory-core` |
| 177 | CLOSED | ZRF-68: add bi-temporal fact versioning (valid-time + transaction-time) to memory store | `hardening` |
| 173 | CLOSED | PR 9: fix(plugin): remove legacy Zeref OS display identity and stale installed payloads | `type:bug`, `hardening`, `P0`, … |
| 164 | CLOSED | epic(zeref): runtime truth, routing, token, retrieval, benchmark, and plugin-install hardening | `epic`, `hardening`, `P0`, … |
| 89 | OPEN | feat(zeref): prompt-leaks integration — target-aware handoff compression (v1.2 umbrella) | `status:blocked`, `audit` |
| 88 | CLOSED | audit(zeref): WS-G — Benchmark & Evidence Reproducibility | `audit` |
| 87 | CLOSED | audit(zeref): WS-F — CI, Release, Versioning, Security Gates | `audit` |
| 86 | CLOSED | audit(zeref): WS-E — Installation & Cross-Surface Portability | `audit` |
| 85 | CLOSED | audit(zeref): WS-B — Registry, Commands, Routing, Team Packs | `audit` |
| 84 | CLOSED | audit(zeref): WS-A — Documentation Archaeology | `audit` |
| 83 | CLOSED | audit(zeref): WS-D — Privacy, Permissions, Network, Security [Opus 4.7] | `audit`, `opus-critical` |
| 82 | CLOSED | audit(zeref): WS-C — Runtime, Memory, Write-Path Integrity [Opus 4.7] | `audit`, `opus-critical` |
| 81 | CLOSED | audit(zeref): Repository-Wide Consistency Audit — umbrella tracker | `audit`, `consistency`, `epic` |
| 73 | CLOSED | release: complete v1.0 trust repair and Zeref Memory Engine rename | `type:feature`, `gate:truth`, … |

**#151 and #152 do not carry `zeref`/`zrf` in title/labels** — they were still pulled per the explicit numbered list in the task brief.

**Individually reviewed issues (`gh issue view <n> --json number,title,state,body`):**

- **#89** (OPEN) — "prompt-leaks integration — target-aware handoff compression (v1.2 umbrella)". Body contains a **local filesystem path**: `` Full plan: local plan file at `~/.claude/plans/activate-zeref-i-want-swirling-flute.md` §ADDENDUM 2. `` — this is a private, machine-specific path (a `~/.claude/plans/` file with a randomly-generated-looking slug) published in a public issue on a public repo. **Flagged.**
- **#151** (OPEN) — "Release merges recreate main/dev divergence". No private URL, path, or unsupported metric found in the body; it's a description of a squash-vs-merge-commit process problem. Clean.
- **#152** (OPEN) — "Repository is inside iCloud-synced Documents, generating conflict copies". Body states: **"The working copy lives under `~/Documents`, which is covered by iCloud Desktop & Documents sync... 351 were present at the last check..."** — this discloses the maintainer's local directory structure (`~/Documents`) and a specific local file-count observation in a public issue. Not a URL or absolute path with a username, but it is local-environment detail exposed publicly. **Flagged as lower-severity** (no leaked path/credential, but reveals local dev setup).
- **#196** (OPEN) — "Retrieval: zeref recall trails a plain BM25 ranker on conversational benchmarks". Body is a benchmark results table (`retrieval_hit_proxy` metric) with an explicit caveat already inline: **"`retrieval_hit_proxy` is an infrastructure signal, not any benchmark's official metric, and must not be quoted as a score."** No private URL/path found; the metric is self-flagged as non-canonical by the issue body itself, so no additional flag needed beyond what the issue already discloses.
- **#208** (OPEN) — "Rename the v1 legacy store path, or document why it keeps the zeref name". No private URL or path; describes `memory/state/zeref.sqlite` staying named `zeref` deliberately for v1→v2 import compatibility, referencing `shiroe/memory/core.py` and `shiroe/storage/importer.py`. Clean.

## 6. Releases, Actions, Wiki, Pages, Packages

`gh release list --repo kanadhiayash/shiroe --limit 50`:

| Title | Latest | Tag | Published |
|---|---|---|---|
| v1.1.1 — CI green-up | Latest | `v1.1.1` | 2026-07-11T22:53:51Z |
| v1.1.0 — audit remediation | | `v1.1.0` | 2026-07-11T12:55:40Z |

Only 2 GitHub Releases exist, both pre-Shiroe-rename (v1.1.x, "zeref"-era). Note this is a **subset** of the 3 tags found in §1 (`v2.0.0-alpha.1`, `v1.1.1`, `v1.1.0`) — `v2.0.0-alpha.1` is a git tag with no corresponding GitHub Release object.

`gh api repos/kanadhiayash/shiroe/branches --jq '.[].name'`: **`main`** only — the remote has exactly one branch. (This confirms the local branch list in §1 is entirely local/unpushed — none of the 16 non-`main`, non-`audit/shr-baseline-evidence` local branches exist on `origin`.)

`gh api repos/kanadhiayash/shiroe/actions/runs --jq '.total_count'`: **1435** total Actions runs recorded.

**Wiki:** `hasWikiEnabled: true` per §4 — enabled, but not cloned/scraped per instruction. Note the `homepageUrl` finding in §4 means the repo's *own* wiki is not what's linked from the repo homepage.

**Pages:** `gh api repos/kanadhiayash/shiroe/pages` → `404 Not Found` ("Get a apiname Pages site"). GitHub Pages is **not enabled** for this repository (a 404 on this endpoint is GitHub's documented signal for "no Pages site configured," not an error).

**Packages:** `gh api repos/kanadhiayash/shiroe/packages` → `404 Not Found`. No repository-scoped packages endpoint/packages exist for this repo. (A user-level packages listing (`gh api users/kanadhiayash/packages`) requires a mandatory `package_type` query param GitHub does not let you omit; not pursued further since it would enumerate the whole user's packages, not this repo's, and is out of scope for a per-repo surface inventory.)

## 7. Findings requiring deferred approval

| # | Surface | Finding | Proposed action | Approval required |
|---|---|---|---|---|
| 1 | Repo settings — `homepageUrl` | Public homepage link points at the legacy `kanadhiayash/zeref-memory-engine` repo's wiki instead of `shiroe`'s own (enabled) wiki or any current doc | Update `homepageUrl` via `gh api -X PATCH repos/kanadhiayash/shiroe -f homepage=...` (or repo Settings UI) to a current-repo target | Yes — settings-change permission, mutating `gh api PATCH` |
| 2 | Repo settings — topics | `work-graph` and `team-sync` topics contradict `README.md:345-346`'s stated limitations (no work-graph module, no multi-device/team story) | Remove or re-scope these two topics via `gh api -X PUT repos/kanadhiayash/shiroe/topics` | Yes — settings-change permission, mutating `gh api PUT` |
| 3 | Current-tree files | Private Notion URL `<redacted-notion-host>/...` live in `CHANGELOG.md`, `GITHUB_OS.md`, `references/v4x-canon/RESEARCH_RESOURCES.md`, `scripts/shiroe-publish-releases.sh` | Redact/replace with a placeholder or internal-only reference | Yes — file edits out of this agent's scope (PR 07 owns history/content decisions); also a judgment call on whether the URL is meant to be public |
| 4 | Full git history (all 235 reachable commits) | The same Notion URL is permanently readable in the object history of every commit across 14 historical file paths (§3), regardless of what's fixed in the current tree | History rewrite (`git filter-repo`/BFG) to purge the string from all blobs, or accept it as permanised and rotate/deprecate the Notion page instead | Yes — irreversible, rewrites all SHAs, force-push required; explicitly out of scope here per task brief ("do NOT rewrite anything; PR 07 owns that decision") |
| 5 | GitHub Issue #89 (public, OPEN) | Body publishes a private local filesystem path: `~/.claude/plans/activate-zeref-i-want-swirling-flute.md` | Edit the issue body to remove/redact the path | Yes — issue edit is a GitHub mutation this agent is barred from performing |
| 6 | GitHub Issue #152 (public, OPEN) | Body discloses maintainer's local dev environment layout (`~/Documents`-based working copy, iCloud sync, a specific "351 conflict copies" count) | Lower priority — informational disclosure, not a credential/URL leak; assess whether it needs redaction or is acceptable as a legitimate bug report | Optional — flagging for awareness, not proposing an edit |
| 7 | GitHub Releases vs tags | `v2.0.0-alpha.1` tag exists in git but has no corresponding GitHub Release object (only 2 Releases exist, both pre-rename `v1.1.x`) | Either publish a Release for `v2.0.0-alpha.1` or confirm it's intentionally unreleased | Yes — `gh release create` is a mutating action |
| 8 | Repo settings — `description` | The public repo description still ends "…handoffs, and **team synchronization**". `fix/shr-active-identity` (SHR-010/011/012) retired that phrase from every in-tree surface: `shiroe/IDENTITY.json` now carries the single canonical description and `scripts/check-version-consistency.py` enforces it across `pyproject.toml`, `.claude-plugin/plugin.json`, and `.claude-plugin/marketplace.json`. The GitHub-side string is now the only surface still making the claim | Set the repo description to the value of `shiroe/IDENTITY.json:.description` via `gh repo edit` or the Settings UI | Yes — settings-change permission, mutating `gh` call |

## Facts

- HEAD at scan time: `a4549e06d3a4b398fb2476039026eda49501176a` on branch `audit/shr-baseline-evidence`.
- 235 commits reachable from all refs; 143 on the current branch; 3 tags; 16 local non-current branches, none of which exist on `origin` (`origin` has only `main`).
- Exactly 91 commits (full history) have `zeref`/`zrf` (case-insensitive) in their subject line — confirmed by direct count, matching the task brief's lead precisely.
- 4 distinct git author identities: one human under 2 name/email pairs, one bot (`dependabot[bot]`).
- The private Notion URL (`<redacted-notion-host>/...`) is real and confirmed present in the **current tree** in exactly 4 files: `CHANGELOG.md`, `GITHUB_OS.md`, `references/v4x-canon/RESEARCH_RESOURCES.md`, `scripts/shiroe-publish-releases.sh` — matching the task brief's lead exactly. It additionally appears, historically only, in 10 other now-changed-or-deleted file paths.
- No real secrets (AWS keys, GitHub PATs, PEM private keys, `sk-`-prefixed API keys) were found anywhere in reachable git history for the 6 credential-shaped patterns scanned; every hit traced to test fixtures, redaction-pipeline source/comments, documentation of the patterns themselves, or base64 image bytes with coincidental substring overlap.
- `homepageUrl` is confirmed pointing at the legacy `zeref-memory-engine` repo's wiki (Lead 1 confirmed).
- Topics `work-graph` and `team-sync` are confirmed present; `work-graph` is explicitly contradicted by `README.md:346`, `team-sync` is implicitly contradicted by `README.md:345` (no line literally says "team-sync") (Lead 2 confirmed with a caveat).
- 73 total issues (16 open / 57 closed); 15 carry legacy `zeref`/`zrf` identity in title or labels.
- Issue #89 leaks a local filesystem path in its public body.
- Only 2 GitHub Releases exist (`v1.1.1`, `v1.1.0`); GitHub Pages is not enabled; no repo-scoped Packages; 1435 total Actions runs recorded; Wiki feature is enabled but its content was not accessed per instruction.

## Assumptions

- "Full mirror history" (SHR-028) is interpreted as `git log --all`/`rev-list --all` on this local clone's refs, which includes `origin/main` plus 16 local-only branches never pushed to `origin`. This clone's remote-tracking state (`origin` has only `main` per the branches API) means the *actual* GitHub-hosted history may differ from what's reachable in this local repo if those 16 local branches were created here and never pushed, or if `origin` has refs not fetched into this worktree. This inventory scanned what is locally reachable, which is the maximal available view but is not independently verified against GitHub's server-side ref list beyond the one `branches` API call in §6.
- The task brief's phrase "README.md:345-346 says are unsupported" was treated as approximately, not literally, true for `team-sync` (see §4) — this is a judgment call, flagged rather than silently corrected or silently accepted.
- Issue #196's `retrieval_hit_proxy` metric was treated as already self-disclosed/caveated by the issue body itself, so it was not additionally flagged as a new finding beyond quoting the existing caveat.

## Unknowns

- Whether `origin` (the actual GitHub-hosted repo) has any refs, branches, or objects not reachable from this local clone's `--all` view — not verifiable without a `git ls-remote` / fresh fetch, which was not part of the specified command set.
- Whether the Notion page at `<redacted-notion-host>/...` is itself set to public or private visibility — this inventory only confirms the URL string's presence in the repo, not the linked page's access control.
- Whether the 16 local-only branches (never pushed to `origin`) are meant to be pushed, are abandoned local work, or are artifacts of this worktree's setup — not established by any read-only command in scope.
- Full content of all 91 legacy-identity commits' diffs was not reviewed line-by-line (only subjects); whether any of them also contain sensitive content beyond the 7 scanned patterns is unknown.

## Risks

- The permanently-readable private Notion URL in history (§3, §7 item 4) is a standing information-disclosure risk for as long as the repo stays public and the history is unrewritten — independent of whether the *current-tree* occurrences (item 3) get cleaned up.
- Issue #89's leaked local path (§7 item 5) is live right now on a public issue; every day it remains is exposure, independent of any Wave 1 PR timeline.
- `homepageUrl` sending visitors to a different (legacy-named) repo's wiki is a trust/credibility risk for anyone landing on the repo page, beyond being merely stale metadata.
- Because `origin` only has a `main` branch (§6) while this local clone carries 16 additional branches, any assumption elsewhere in the Wave 1 program that those branches are "on GitHub" and inspectable/actionable via `gh` would be incorrect — they are local-only.
