# Shiroe Execution Log

## How to read this file

PR 01's entry below was written live, during execution. **Entries for PRs 02–07
were backfilled** after Wave 1 merged, and say so. Backfilled entries carry only
what the repository can still prove — commit SHAs, authored dates, file
statistics, backlog IDs quoted from the commit bodies, merged PR numbers, and
suite results re-measured by checking each commit out and running it. Fields
that were never recorded and cannot be reconstructed are marked
*not recorded* rather than estimated.

Suite results in the backfilled entries were re-measured on 2026-08-04 against
Python 3.11.15 / pytest 9.1.1 in a detached worktree, one checkout per commit.
They are today's result for that tree, not necessarily what the author saw.

---

## Entry

- **Timestamp:** 2026-08-04T04:28:04Z
- **Wave:** 1
- **PR:** 01
- **Branch:** `audit/shr-baseline-evidence`
- **Starting commit:** `a4549e06d3a4b398fb2476039026eda49501176a`
- **Ending commit:** recorded on commit (see `git log -1` for this branch)
- **Backlog IDs:** SHR-003, SHR-004, SHR-005, SHR-006, SHR-028, SHR-030

### Files changed

Eight files added. **Zero existing files modified** (`git diff --stat` empty on tracked files).

```
docs/canon/SOURCE_AUTHORITY.md          SHR-003 authority hierarchy (prose + tagged JSON block)
docs/canon/canon-baseline.json          SHR-004 acknowledged-findings baseline
docs/canon/PUBLIC_CLAIM_LEDGER.json     SHR-006 claim -> evidence ledger
docs/canon/SHIROE_BASELINE.md           preflight evidence, bound to a4549e0
docs/canon/GITHUB_SURFACE_INVENTORY.md  SHR-028/030 history + non-Git surface scan
docs/canon/SHIROE_EXECUTION_LOG.md      this file
scripts/check-canon-consistency.py      the gate
tests/test_canon_consistency.py         21 tests
```

### Focused tests

`tests/test_canon_consistency.py` — 21 tests, all passing.

TDD order held: the test file was written first and run against an empty tree. Result: **19 failed, 2 passed**, every failure `No such file or directory` on the not-yet-written script. The 2 passers (`test_missing_authority_map_exits_2`, `test_acknowledgement_without_owner_exits_2`) passed vacuously — a missing script also exits 2 — and were pinned down by the clean-tree exit-0 test once the script existed.

Anti-vacuity proof, run manually: appended `Canonical state is markdown on disk.` to `QUICKSTART.md` (active rank-6 surface) →

```
✘ 1 error(s):
  - NEW: QUICKSTART.md::markdown-canonical [SHR-004] Canonical state is markdown
EXIT=1
```

Reverted; byte-identical to pre-injection backup; audit back to exit 0.

### Full test result

| | Result |
|---|---|
| Baseline at `a4549e0`, no changes | 978 passed, 1 skipped |
| After this PR | **999 passed, 1 skipped**, exit 0 |

Delta is exactly +21 — this PR's tests. No pre-existing test changed state.

Regression set (the guards most at risk): `test_doc_freshness`, `test_validator`, `test_vnext_pr20_public_surface`, `test_claim_gate` — 30 passed.

### Validation result

```
python scripts/shiroe-validate.py            -> exit 0  "✔ Validation passed"
python scripts/check-version-consistency.py  -> exit 0  "All surfaces aligned on 3.0.0-alpha.1"
python scripts/check-canon-consistency.py    -> exit 0  "✔ Canon audit passed (21 acknowledged, no drift)"
git diff --check                             -> clean
```

### Privacy result

```
python -m shiroe audit-privacy --strict --fail-classes credentials
-> exit 0  "✔ 0 hits in zero-tolerance class(es) credentials (101 informational hits in non-blocking classes)"
```

**A privacy defect was found and fixed in this PR's own artifacts before commit.** As first written by the evidence subagents, `SHIROE_BASELINE.md` embedded the operator's absolute home path 12 times and `GITHUB_SURFACE_INVENTORY.md` republished the live private Notion URL 6 times — i.e. the audit reproduced exactly the two leak classes the program (SHR-022) exists to remove, and which `REDACT.md` classes `internal_paths` forbid. Redacted to `<repo>`, `<home>`, `<redacted:private-notion-url>`, `<redacted-notion-host>`. Residual hits: 0. File:line references to the leaks in the *source* tree are preserved, so the findings stay actionable without carrying the values.

### Release-check result

Not run as a gate in this PR. Reason recorded under Facts: `shiroe release check` invokes pytest as a subcommand and its `test_suite` sub-check fails in the clean py3.11 venv for the same missing-pytest reason described below. Running it would produce a failure attributable to the preflight recipe, not to this PR. Deferred to PR 02, which should run it after the venv recipe is corrected.

---

### Facts

1. `HEAD` == `main` == `origin/main` == `a4549e06d3a4b398fb2476039026eda49501176a`, matching the handoff's expected baseline. Worktree was clean at start.
2. **The handoff's preflight cannot run the test suite as written.** `python -m pip install -e .` never installs `pytest` — no dependency or extra covers it (`pyproject.toml` `dependencies = []`; no `test` extra). In a clean py3.11 venv, `pytest --collect-only`, `pytest -q`, and `release check`'s `test_suite` all fail with `No module named pytest`. CI works only because `.github/workflows/shr-verify.yml` installs pytest as a separate explicit step the preflight omits. Preflight/CI drift, not a code defect.
3. Baseline test result was first obtained on **python3.14.4 — out of the declared support matrix** (3.11/3.12/3.13), with no venv and no install, because system pytest happened to be present and `shiroe` imported from cwd. The in-matrix py3.11 figure was obtained only after `pip install pytest` was added to the venv by hand.
4. `tests/test_benchmark_suite.py::test_run_all_is_idempotent` **writes to the git-tracked `docs/BENCHMARK_REPORT.md`** and restores only `benchmarks/results.json` in its `finally`. Every full-suite run dirties the tree, breaking the `git status --short` gate this program's own verification matrix depends on. Reverted after each run here; not fixed (out of scope for an audit PR). Spun off as a separate task.
5. `pytest.ini` already sets `addopts = -q`; the preflight's own `-q` stacks to `-qq` and suppresses the summary line. Run bare `pytest` for counts.
6. **`docs/audits/` is guard-locked.** `tests/test_doc_freshness.py:108` asserts it tracks only `README.md`, and `:87` bans any date-stamped filename anywhere under `docs/`. The program's literal artifact paths would have turned CI red on commit. Artifacts were placed under a new `docs/canon/` instead (owner-approved). Zero existing tests edited.
7. `README.md:263`'s "lists all 31" is **correct**, contrary to the initial recon finding: 28 top-level subparsers in `shiroe/cli.py` plus one each in `cli_benchmark.py`, `cli_capability.py`, `cli_providers.py` = 31, confirmed against `shiroe --help`. Ledgered `verified`.
8. `README.md:122` claims "82 files"; the tree has 83. Ledgered `contradicted`.
9. A permanent `dev` branch exists (primary clone checked out on it at `0c2e81d`), plus 16 local branches. `origin` carries only `main` — none of the 16 were ever pushed. Contradicts the intended main-only model. **PR 06 owns this.**
10. Public repo metadata: `homepageUrl` points at the legacy `kanadhiayash/zeref-memory-engine` wiki; topics include `work-graph` and `team-sync`, both disclaimed as unsupported by `README.md:345-346`.
11. Full-history secret scan across all 235 reachable commits (`notion.site`, `notion.so`, `AKIA`, `BEGIN RSA`, `BEGIN OPENSSH`, `ghp_`, `sk-`): **no real credentials**. Every AKIA/RSA/`ghp_`/`sk-` hit traced to test fixtures or redaction-pipeline documentation. The private Notion URL is the one genuine finding — real, in 4 current-tree files and 10 historical-only paths.
12. 91 commits carry `zeref`/`zrf` in their subject. 280 line-hits across 45 current-tree files. 73 issues (16 open / 57 closed), 15 carrying legacy identity.
13. Issue **#89** leaks a local filesystem path in its public body; issue **#152** discloses local dev-environment detail (iCloud-synced working copy).
14. SHR-003 gate met outright: 533 files scanned — 285 active, 8 archived, 240 unscoped, **0 unclassified, 0 ambiguous-authority, 0 dead globs**.
15. SHR-005: `skills` 15/15 and `agents` 6/6 carry a status label; `commands` 0/8, `team_packs` 0/9, `gates` 0/5 carry none — the schema defines the enum only under `skills` and `agents`, so the other three have nowhere to declare one.

### Assumptions

- `docs/canon/` is an acceptable home for program evidence given the `docs/audits/` guard. Recorded as a deviation from the handoff's literal paths, not a silent substitution.
- The 21 baseline findings are all genuinely deferred to later PRs, not suppressed. Each names an `owner` and a `resolving_pr`; the checker exits 2 on any acknowledgement lacking them.
- Recording the acknowledged findings does not itself satisfy SHR-004/005/006 — those close when the findings are fixed and removed from the baseline.

### Unknowns

- Whether the suite passes on python3.12 and 3.13. Neither interpreter is installed on this machine; only 3.11 and 3.14 were exercised.
- Whether the Notion page is itself public or private. This inventory confirms the URL string's presence in the repo, not the linked page's access control.
- Whether the owner wants a history rewrite for the Notion URL (PR 07 decision) or accepts it as historical lineage.
- Whether `references/v4x-canon/SHIROE_OS.md` is genuinely archived. `CLAUDE.md` still cites its §0 for the session reading order, and `shiroe/release/claim_gate.py` — rank-1 code — derives behaviour from that directory. PR 03 must decide.

### Risks

- Regex-based contradiction detection can over- or under-fire on prose. Mitigated by sentence bounding, a line-level `generated|derived|views?|never canonical` exculpation guard, and a three-point synthetic proof (fires / doesn't over-fire / respects archived scope). Tuning was driven by four real false positives on this tree, not invented.
- The baseline file is an escape hatch. Mitigated two ways: exit 2 on an acknowledgement without an owner, and a `DROPPED` error that makes PR 02 unable to go green without deleting the entries it fixes. The acknowledgement is a debt record that must be actively repaid.
- Every full-suite run currently dirties `docs/BENCHMARK_REPORT.md` (Fact 4). Until fixed, the `git status --short` gate is unreliable for any PR that runs the suite.

### Deferred approval actions

None taken. All require explicit authorization:

| Action | Owner |
|---|---|
| Push branch, open/merge PR, tag, release | — |
| GitHub metadata: fix `homepageUrl`; remove `work-graph` / `team-sync` topics | PR 03 / SHR-010, SHR-011 |
| Sanitize issue #89 (local path) and #152 (local env detail) | PR 05 / SHR-023, SHR-024 |
| Rename legacy-identity issue titles (15) | PR 05 / SHR-026 |
| Remove private Notion URL from `CHANGELOG.md`, `GITHUB_OS.md`, `references/v4x-canon/RESEARCH_RESOURCES.md`, `scripts/shiroe-publish-releases.sh` | PR 05 / SHR-022 |
| Remove the `<redacted:operator-path>` hardcode in `scripts/shiroe-cleanup-branches.sh:15` | PR 05 / SHR-022 |
| Retire `dev` and the 16 stale local branches | PR 06 / SHR-025 |
| Any history rewrite or force push | PR 07 / SHR-029, SHR-031 |

### Rollback

All eight files are new and untracked before commit; no existing file was modified. To revert:

```bash
git reset --hard a4549e06d3a4b398fb2476039026eda49501176a
rm -rf docs/canon scripts/check-canon-consistency.py tests/test_canon_consistency.py
```

No migration, no schema change, no generated artifact. Reverting restores the exact `a4549e0` tree.

### Review status

Two-stage review was **not completed**. Both review subagents (spec compliance, then code quality and security) terminated on an API session limit before producing a verdict. The lead performed the privacy scan, the audit-only diff verification, the ledger accuracy check, and the full gate run directly — findings above. **The independent code-quality and security review of `scripts/check-canon-consistency.py` remains outstanding and must run before this branch is pushed.**

---

## Entry — PR 02 (backfilled)

- **Timestamp:** 2026-08-04T08:55:59Z (authored); merged 2026-08-04T16:15:49Z
- **Wave:** 1
- **PR:** 02 — [#216](https://github.com/kanadhiayash/shiroe/pull/216) "Wave 1 PR 02: canonical state and graph projection boundary"
- **Branch:** `fix/shr-canonical-state`
- **Starting commit:** `85ca54a` (PR 01 tip)
- **Ending commit:** `95a34122ff364390849fcb623fa4e23a9f849be3`
- **Backlog IDs:** SHR-001, SHR-002, SHR-008

### Files changed

Three commits, because two of them repair the gate PR 01 had just shipped:

| Commit | Subject | Stat |
|---|---|---|
| `193182e` | make SQLite/JSONL the stated canonical store everywhere | 8 files, +318 −67 |
| `27bedaa` | scope contradiction exculpation to the clause, not the line | 2 files, +77 −5 |
| `95a3412` | bind acknowledgements to their matched text; see marked-up claims | 3 files, +126 −17 |

Added: `tests/test_canonical_state_contract.py`, `docs/adr/ADR-0006-graph-projection-invariant.md`.

### Focused tests

`tests/test_canonical_state_contract.py` — asserts the ADR-0001 invariant holds on
every active surface, importing the prose detectors from the gate rather than
restating them.

### Full test result

| Tree | Result |
|---|---|
| `85ca54a` (PR 01 tip) | 999 passed, 1 skipped |
| `193182e` | 1008 passed, 1 skipped |
| `27bedaa` | 1015 passed, 1 skipped |
| `95a3412` (PR 02 tip) | **1024 passed, 1 skipped** |

### Facts

- Two of this PR's three commits are corrections to PR 01's own gate, found while
  using it: `EXCULPATING_RE` was matched against the whole line, so appending one
  qualifying word anywhere on it silenced a real contradiction, and a Markdown
  table row let one cell's "generated" exculpate a contradiction in another. It is
  now scoped to the clause containing the hit.
- Finding identity was `(surface, rule)` and drift was `count` alone, so swapping
  an acknowledged contradiction for a *different* one of the same rule on the same
  surface kept count at 1 and stayed `[KNOWN]`. Every acknowledgement was a
  laundering slot. Findings now carry a content `digest`.
- Claim shapes were blind to Markdown emphasis, so a bolded `**979** tests` read
  as unledgered while a plain one did not.

### Unknowns

Validation, privacy and release-check output for this PR were not recorded and
cannot be reconstructed — those commands report on a tree, and the tree has moved.

### Deferred approval actions

Carried forward unchanged from PR 01.

### Rollback

`git revert 95a3412 27bedaa 193182e`. No migration, no schema change.

### Review status

*Not recorded.*

---

## Entry — PR 03 (backfilled)

- **Timestamp:** 2026-08-04T10:05:35Z (authored); merged 2026-08-04T16:14:22Z
- **Wave:** 1
- **PR:** 03 — [#217](https://github.com/kanadhiayash/shiroe/pull/217) "Wave 1 PR 03: active identity, terminology, and sequence migration"
- **Branch:** `fix/shr-active-identity`
- **Starting commit:** `95a3412`
- **Ending commit:** `3bb62ec3bcdddcfb3ab95f40345870cc59e78146`
- **Backlog IDs:** SHR-007, SHR-009, SHR-010, SHR-011, SHR-012, SHR-013, SHR-017, SHR-018, SHR-019, SHR-027, SHR-032

### Files changed

55 files, +735 −211. Added `tests/test_active_identity.py`,
`tests/test_execution_sequence_compat.py`, `scripts/check-active-identity.py`.

### Focused tests

`tests/test_active_identity.py` — the identity scan's own contract, including that
the allowlist may only shrink without a written reason.

### Full test result

**1047 passed, 1 skipped** (from 1024).

### Facts

- Legacy identifiers were not globally replaced. They remain legitimate in
  `CHANGELOG.md`, `docs/adr/`, `MIGRATION.md` and archived canon; the scan
  distinguishes active surfaces from archived prefixes rather than banning a
  string repository-wide.
- `references/v4x-canon/**` carries `Superseded` markers from this PR onward, which
  is what lets the canon gate silence it without silencing accepted ADRs.

### Unknowns

Validation, privacy and release-check output not recorded.

### Rollback

`git revert 3bb62ec`.

### Review status

*Not recorded.*

---

## Entry — PR 04 (backfilled)

- **Timestamp:** 2026-08-04T10:26:42Z (authored); merged 2026-08-04T16:16:03Z
- **Wave:** 1
- **PR:** 04 — [#218](https://github.com/kanadhiayash/shiroe/pull/218) "Wave 1 PR 04: legacy compatibility isolation and removal policy"
- **Branch:** `fix/shr-compatibility-boundary`
- **Starting commit:** `3bb62ec`
- **Ending commit:** `be7c5ead0a1fc0b74aa9c716bbf931fefd188e1b`
- **Backlog IDs:** SHR-014, SHR-015, SHR-016, SHR-027

### Files changed

26 files, +847 −133. Added `shiroe/compat/` (`__init__.py`, `legacy_identity.py`),
`docs/DEPRECATIONS.md`, `tests/test_legacy_compatibility_boundary.py`.

### Full test result

**1063 passed, 1 skipped** (from 1047).

### Facts

- Legacy identity moved behind a single boundary module instead of being spread
  across `env.py`, `memory/core.py`, `storage/state.py`, `policy/loader.py` and
  five others. The boundary is what makes a later removal a one-file change.
- `memory/state/zeref.sqlite` was **not** renamed. It is a real on-disk v1 file,
  and renaming it would leave two Shiroe-named databases both claiming to be
  current state — which `tests/test_store_convergence.py` exists to prevent. The
  fix is store convergence (import rows, then drop), tracked as issue #208.

### Unknowns

Validation, privacy and release-check output not recorded.

### Rollback

`git revert be7c5ea`. Note this restores legacy identity handling to its scattered
form; it does not touch any on-disk database.

### Review status

*Not recorded.*

---

## Entry — PR 05 (backfilled)

- **Timestamp:** 2026-08-04T10:42:51Z (authored); merged 2026-08-04T16:14:27Z
- **Wave:** 1
- **PR:** 05 — [#219](https://github.com/kanadhiayash/shiroe/pull/219) "Wave 1 PR 05: redundant files, stale scripts, ownership, private references"
- **Branch:** `chore/shr-repository-cleanup`
- **Starting commit:** `be7c5ea`
- **Ending commit:** `8a736ad60a05525c49b8b113eb52293cbe9e0004`
- **Backlog IDs:** SHR-020, SHR-021, SHR-022, SHR-023

### Files changed

15 files, +473 −611 — the only net-negative PR in Wave 1. Added
`tests/test_no_private_operational_references.py` and `.github/CODEOWNERS`;
deleted the duplicate root `CODEOWNERS` and two stale scripts.

### Full test result

**1076 passed, 1 skipped** (from 1063).

### Facts

- The private Notion URL was removed from the current tree in four places
  (`CHANGELOG.md`, `GITHUB_OS.md`, `references/v4x-canon/RESEARCH_RESOURCES.md`,
  `scripts/shiroe-publish-releases.sh`). Removal from the tree is not removal from
  history — that question is PR 07's.
- `scripts/shiroe-cleanup-branches.sh` hardcoded an operator home directory.

### Deferred approval actions

GitHub issue edits (#89, #152, #196) were written up as approval-ready work orders
in `docs/canon/GITHUB_ISSUE_ACTIONS.md` and **not executed**. Still outstanding.

### Rollback

`git revert 8a736ad`. Restores the deleted files.

### Review status

*Not recorded.*

---

## Entry — PR 06 (backfilled)

- **Timestamp:** 2026-08-04T14:31:10Z (authored); merged 2026-08-04T16:14:31Z
- **Wave:** 1
- **PR:** 06 — [#220](https://github.com/kanadhiayash/shiroe/pull/220) "Wave 1 PR 06: protected main plus short-lived branches"
- **Branch:** `ci/shr-main-only-trunk`
- **Starting commit:** `8a736ad`
- **Ending commit:** `6ffbc74c59ade7b1de31853b84807b9f359ed455`
- **Backlog IDs:** SHR-025

### Files changed

8 files, +453 −32. Added `docs/BRANCHING.md`,
`.github/workflows/branch-retention.yml`, `tests/test_workflow_branch_policy.py`.

### Full test result

**1099 passed, 1 skipped** (from 1076).

### Facts

- The branching policy is enforced by a test over workflow *content*, not by
  documentation alone — `tests/test_workflow_branch_policy.py` fails if a workflow
  reintroduces a permanent `dev`.
- The local `dev` branch and the stale local branches were not deleted by this PR;
  the policy forbids restoring a permanent `dev` going forward.

### Unknowns

Validation, privacy and release-check output not recorded.

### Rollback

`git revert 6ffbc74`.

### Review status

*Not recorded.*

---

## Entry — PR 07 (backfilled)

- **Timestamp:** 2026-08-04T15:04:12Z (authored); merged 2026-08-04T16:16:16Z
- **Wave:** 1
- **PR:** 07 — [#221](https://github.com/kanadhiayash/shiroe/pull/221) "Wave 1 PR 07: history redaction decision package"
- **Branch:** `security/shr-redaction-manifest`
- **Starting commit:** `6ffbc74`
- **Ending commit:** `00a5c8202cb61e0eb1fd54e50ec408d676361e56`
- **Backlog IDs:** SHR-022, SHR-029, SHR-031

### Files changed

| Commit | Subject | Stat |
|---|---|---|
| `e4a3099` | classify every sensitive-data candidate; rewrite nothing | 8 files, +1301 −3 |
| `00a5c82` | defang the three literals the tree guard caught once tracked | 3 files, +18 −6 |

Added `docs/security/HISTORY_REDACTION_MANIFEST.md`,
`docs/security/HISTORY_REWRITE_RUNBOOK.md`, `scripts/scan-history-sensitive.sh`,
`tests/test_redaction_manifest.py`.

### Full test result

| Tree | Result |
|---|---|
| `6ffbc74` | 1099 passed, 1 skipped |
| `e4a3099` | **2 failed**, 1108 passed, 1 skipped |
| `00a5c82` (Wave 1 tip) | **1110 passed, 1 skipped** |

The intermediate commit `e4a3099` was red. Failures:

```
FAILED tests/test_no_private_operational_references.py::test_tracked_tree_has_no_private_operational_references
FAILED tests/test_redaction_manifest.py::test_current_tree_cleanup_claims_are_true
```

Both were the new guard catching literal example strings inside the manifest that
this same commit shipped — the guard working, on its own documentation. `00a5c82`
defanged the three literals. Wave 1's tip is green; `e4a3099` alone is not, and
must not be used as a base.

### Facts

- The scan classified every sensitive-data candidate across history and
  **rewrote nothing**. A strict-shape re-scan of all 2944 blobs found **zero real
  credentials** anywhere in history.
- The private Notion pages were deleted by the owner, so the URL in history is a
  dead link, not a live leak. It sits at the tip of 21 of 29 refs across 224 of 243
  commits; rewriting that to scrub a dead URL would break every tag, fork,
  signature and existing clone for no security gain.
- Two blobs carrying the URL are **unreachable** — `rev-list --all` cannot see
  them — so `filter-repo` alone would not remove them; they need
  `reflog expire` + `gc --prune`.

### Decision

**No history rewrite.** `docs/security/HISTORY_REWRITE_RUNBOOK.md` exists and is
ready if the owner explicitly reverses this; it requires written approval of a
specific manifest version. This decision is recorded so it is not re-litigated.

### Deferred approval actions

- Any history rewrite or force-push to `main` — still unauthorised.
- GitHub issue edits #89, #152, #196 — still outstanding, see PR 05.

### Rollback

`git revert 00a5c82 e4a3099`. Documentation and one scan script; no code path
changes.

### Review status

*Not recorded.*

---

## Wave 1 summary

| | Start (`a4549e0`) | End (`00a5c82`) |
|---|---|---|
| Suite | 978 passed, 1 skipped | **1110 passed, 1 skipped** |
| Canon findings | 21 | **5** |
| Identity allowlist | 33 | **17** |
| Backlog items closed | — | **32 of 136** |

Seven PRs, [#215](https://github.com/kanadhiayash/shiroe/pull/215)–[#221](https://github.com/kanadhiayash/shiroe/pull/221), all merged. Verified on merged `main`, not on the branches.

Known process defect during Wave 1: `tests/test_benchmark_suite.py::test_run_all_is_idempotent`
rewrote the tracked `docs/BENCHMARK_REPORT.md` on every full-suite run, so
`git status --short` — itself a gate command — was dirty on all seven PRs and was
reverted by hand each time. Fixed after Wave 1 in
[#222](https://github.com/kanadhiayash/shiroe/pull/222).
