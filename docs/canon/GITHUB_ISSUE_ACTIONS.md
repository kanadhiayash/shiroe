# GitHub issue actions — approval-ready (SHR-023, SHR-024, SHR-025, SHR-026)

**Status:** proposed, **nothing executed**. Every action below is a mutating
GitHub call. The agent that produced this file had no authorization to run one,
so this is a work order for a human, not a record of work done.

**Provenance.** Issue state, titles and body quotes are taken from
`docs/canon/GITHUB_SURFACE_INVENTORY.md` §5 and §7, captured at commit
`a4549e06d3a4b398fb2476039026eda49501176a` via `gh issue list` / `gh issue view`.
No `gh` call, read or write, was made while writing this file. **Re-read each
issue before acting** — the quotes below are a snapshot, not live state.

**Why here and not `docs/audits/`.** The program names
`docs/audits/GITHUB_ISSUE_ACTIONS.md`, but `docs/audits/` is guard-locked:
`tests/test_doc_freshness.py` asserts it tracks only `README.md`. This file
lives with the rest of the program's evidence in `docs/canon/` instead.

**Relationship to `GITHUB_SURFACE_INVENTORY.md`.** That file is the *inventory*
— it records what was found. This file is the *action list* — what to do about
it. Deferred-approval rows 5 and 6 there correspond to issues #89 and #152
here; they are cross-referenced, not restated in full.

---

## 1. Issue #89 — leaks a local plan-file path (SHR-023)

| | |
|---|---|
| **Number** | #89 |
| **State** | OPEN |
| **Current title** | `feat(zeref): prompt-leaks integration — target-aware handoff compression (v1.2 umbrella)` |
| **Labels** | `status:blocked`, `audit` |
| **Verdict** | **Redact body + edit title** |
| **Severity** | High — private path published on a public repo |
| **Cross-ref** | `GITHUB_SURFACE_INVENTORY.md` §7 row 5 |

**What is leaked.** The body publishes a machine-local plan file path:

> Full plan: local plan file at `~/.claude/plans/activate-zeref-i-want-swirling-flute.md` §ADDENDUM 2.

Two problems in one line. The path names a file on the maintainer's own
workstation, so it is useless to every reader and informative only to someone
profiling the maintainer's setup. And it makes a *public* issue's plan of
record unreadable — the issue defers its own substance to a document nobody
outside that machine can open.

**Proposed edit.** Replace that sentence with either the substance or an
in-repo pointer, and drop the path. Suggested replacement:

> Full plan: maintained outside this repository. The parts that bind this issue
> are restated inline below.

If the plan content is worth keeping, inline the ADDENDUM 2 section into the
issue body rather than linking to it.

**Title.** Also carries the legacy `zeref` identity, so this issue is one of
the 15 in the SHR-026 batch (§3 below). Proposed:
`feat(shiroe): prompt-leaks integration — target-aware handoff compression (v1.2 umbrella)`

**Command (for the approver to run, not the agent):**

```
gh issue edit 89 --repo kanadhiayash/shiroe \
  --title 'feat(shiroe): prompt-leaks integration — target-aware handoff compression (v1.2 umbrella)' \
  --body-file <edited-body.md>
```

**Note on residue.** GitHub keeps an edit history on issue bodies, visible to
anyone who can read the issue. Editing removes the path from the current view,
not from the edit log. If the path must be unrecoverable, the issue has to be
deleted and reopened — that is a separate, heavier decision and is **not**
proposed here.

---

## 2. Issue #152 — discloses local dev-environment layout (SHR-024)

| | |
|---|---|
| **Number** | #152 |
| **State** | OPEN |
| **Current title** | `Repository is inside iCloud-synced Documents, generating conflict copies` |
| **Labels** | (none legacy-relevant) |
| **Verdict** | **Redact body — keep the issue open** |
| **Severity** | Low — environment detail, no path or credential |
| **Cross-ref** | `GITHUB_SURFACE_INVENTORY.md` §7 row 6 |

**What is disclosed.** The body states:

> The working copy lives under `~/Documents`, which is covered by iCloud
> Desktop & Documents sync... 351 were present at the last check...

`~/Documents` is a standard platform directory and names no person; on its own
it is not a leak. What is disclosed is the *conjunction*: that the maintainer's
only working copy sits in a cloud-synced personal folder, plus a specific
count of stray files on that machine. That is a profile of one workstation
published on a public repo.

**This is also the only issue whose leak is load-bearing.** The bug *is* the
sync location — redact it entirely and the report stops making sense. So the
edit has to keep the mechanism and drop the personal specifics.

**Proposed edit.** Rewrite the environment sentence generically:

> The working copy lives inside a cloud-synced user directory (macOS Desktop &
> Documents sync). The sync agent creates conflict copies of files the tooling
> writes concurrently; hundreds accumulated before this was noticed.

Changes: `~/Documents` → "a cloud-synced user directory"; the exact
`351` count → "hundreds". Both preserve the report; neither describes a
specific machine.

**Keep open.** This is a legitimate, unresolved bug about repository placement.
The redaction is orthogonal to the fix.

**Command:**

```
gh issue edit 152 --repo kanadhiayash/shiroe --body-file <edited-body.md>
```

---

## 3. Issue #196 and the legacy-identity title batch (SHR-026)

| | |
|---|---|
| **Number** | #196 (plus 14 others) |
| **State** | OPEN |
| **Current title** | `Retrieval: zeref recall trails a plain BM25 ranker on conversational benchmarks` |
| **Labels** | `area:memory-core` |
| **Verdict** | **Edit title** — no redaction, nothing to close |
| **Severity** | Cosmetic/naming — no private data |
| **Cross-ref** | `GITHUB_SURFACE_INVENTORY.md` §5 issue table (15 rows) |

**What is stale.** The title names the product `zeref`. Since the rename,
`scripts/check-active-identity.py` enforces Shiroe naming on every active
in-tree surface; issue titles are an active public surface the in-tree gate
cannot reach. #196's *body* is clean — the inventory notes it already carries
its own caveat, `` "`retrieval_hit_proxy` is an infrastructure signal, not any
benchmark's official metric, and must not be quoted as a score." `` — so this
is a title-only edit.

**Proposed edit for #196:**
`Retrieval: shiroe recall trails a plain BM25 ranker on conversational benchmarks`

```
gh issue edit 196 --repo kanadhiayash/shiroe \
  --title 'Retrieval: shiroe recall trails a plain BM25 ranker on conversational benchmarks'
```

**The other 14.** `GITHUB_SURFACE_INVENTORY.md` §5 lists all 15 issues carrying
`zeref`/`zrf` in title or labels. They split into two groups, and the split
matters:

* **OPEN (3: #208, #196, #89)** — live work items. Rename these. #208 is the
  one exception in the group: its title
  (`Rename the v1 legacy store path, or document why it keeps the zeref name`)
  is *about* the legacy name, so the token is the subject, not a stale label.
  **Leave #208's title alone.**
* **CLOSED (12: #177, #173, #164, #88, #87, #86, #85, #84, #83, #82, #81, #73)**
  — historical records of work done under the old name. Renaming them would
  falsify what was actually filed, for the same reason
  `check-active-identity.py` exempts `CHANGELOG.md` and `MIGRATION.md`.
  **Do not rename closed issues.**

Net: **3 title edits** (#89, #196, and #208 only if the owner disagrees with
the reasoning above), not 15.

---

## 4. Branch protection on `main` (SHR-025)

| | |
|---|---|
| **Surface** | Repository rulesets, not an issue |
| **Verdict** | **Enable `protect-main-soft`; delete the retired-branch ruleset** |
| **Severity** | High — the trunk this repository documents as protected is not protected |
| **Cross-ref** | `docs/BRANCHING.md`; `docs/RELEASE_VERDICT_3.0.0-alpha.1.md` §"Re-select the required status checks" |

**Provenance.** Three read-only calls made while writing this section, on
`ci/shr-main-only-trunk` at `3da7ff2`. No mutating call was made.

```
gh api repos/kanadhiayash/shiroe/branches --jq '.[].name'
gh api repos/kanadhiayash/shiroe/rulesets
gh api repos/kanadhiayash/shiroe/branches/main/protection
```

**What was found.**

| Ruleset | Target | Enforcement |
|---|---|---|
| `protect-dev-soft` (id `18747477`) | `refs/heads/dev` | **disabled** |
| `protect-main-soft` (id `18747523`) | `refs/heads/main` | **disabled** |
| `protect-release-tags` (id `18747540`) | tags | active |

`gh api .../branches` returns exactly one name, `main` — the remote is already
main-only, which is what PR 06 asserts in code and docs. But
`.../branches/main/protection` returns `404 Branch not protected`, and the
ruleset that would protect it is switched off. So today the trunk can be
force-pushed and deleted, and `protect-main-soft`'s `pull_request` rule — the
one that would stop a direct push — never evaluates.

The second finding is the retired-branch ruleset. `protect-dev-soft` still
targets `refs/heads/dev`, a ref that no longer exists on the remote. Disabled
and pointed at nothing, it is inert; its cost is that the next person to read
the ruleset list will reasonably conclude the two-branch model is still live.

**Third: `protect-main-soft` permits merge commits.** Its `allowed_merge_methods`
is `["merge", "squash", "rebase"]`. `docs/BRANCHING.md` requires squash-and-merge,
and merge commits are the mechanism issue #151 records as producing the
divergence that PR 06 exists to retire. Configuration and doctrine disagree, and
right now the configuration is the one nobody is enforcing.

**Proposed changes, in order.**

1. Set `protect-main-soft` enforcement to `active`.
2. Narrow its `allowed_merge_methods` to `["squash"]`.
3. Add the `required_status_checks` rule and select the `Shiroe Verify` jobs
   (`Validate`, `pytest`, `version-consistency`, `privacy`, `benchmarks`,
   `release-check`, `e2e`, `doc-freshness`). The v3.0.0-alpha.1 release verdict
   already recorded that the required checks were never re-selected; that item
   is still open.
4. Delete `protect-dev-soft`.

**Commands (for the approver to run, not the agent):**

```
gh api -X PUT repos/kanadhiayash/shiroe/rulesets/18747523 --input <edited-ruleset.json>
gh api -X DELETE repos/kanadhiayash/shiroe/rulesets/18747477
```

**Why this is not done here.** All four are mutating repository-administration
calls. Enabling enforcement changes who can push to the trunk and could lock the
maintainer out of an in-flight workflow; deleting a ruleset is not reversible
from the API. Neither belongs to an agent.

**What PR 06 could do without approval** is everything in-tree: the workflows,
`docs/BRANCHING.md`, `CONTRIBUTING.md`, `GITHUB_OS.md`, and
`tests/test_workflow_branch_policy.py`. Those are done. The gate "protected
`main` plus short-lived branches is consistently *configured* and documented" is
therefore met on the documented half and blocked on the configured half, by
design.

---

## Summary

| Issue | Leaked / stale | Action | Approval |
|---|---|---|---|
| #89 | Local plan-file path in body; legacy title | Redact body + edit title | Required — mutating `gh issue edit` |
| #152 | Cloud-synced working-copy location + local file count | Redact body, keep open | Required — mutating `gh issue edit` |
| #196 | Legacy `zeref` in title | Edit title | Required — mutating `gh issue edit` |
| #208 | Legacy `zeref` in title, but it is the subject | **No action** | — |
| 12 closed legacy-titled issues | Legacy `zeref` in title | **No action** — historical record | — |
| Ruleset `protect-main-soft` | Disabled; permits merge commits; no required checks | Enable, restrict to squash, select `Shiroe Verify` checks | Required — mutating `gh api -X PUT` |
| Ruleset `protect-dev-soft` | Targets a ref that no longer exists | Delete | Required — mutating `gh api -X DELETE` |

**Nothing here is closed.** No issue in this set is stale enough to close: #89
and #152 describe unresolved problems and #196 is an open benchmark finding.
Redaction and renaming do not resolve them.

## Open questions for the approver

- Is the edit-history residue on #89 acceptable, or does the path need to be
  unrecoverable (which means deleting and refiling the issue)?
- Should closed issues be renamed for searchability despite falsifying the
  record? This file recommends no.
- #208 asks whether `memory/state/zeref.sqlite` keeps its name. That decision
  is upstream of its title and is not proposed here.
