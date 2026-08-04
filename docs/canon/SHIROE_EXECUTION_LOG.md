# Shiroe Execution Log

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
