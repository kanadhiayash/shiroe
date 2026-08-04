# Shiroe Baseline — Wave 1 / PR 01

- Recorded at commit: `a4549e06d3a4b398fb2476039026eda49501176a` (full sha)
- Recorded at (UTC): `2026-08-04T00:21:27Z`
- Branch: `audit/shr-baseline-evidence`
- Baseline interpreter: Python 3.11.15 (in CI matrix `['3.11', '3.12', '3.13']`, confirmed in `.github/workflows/shr-verify.yml` lines 24 and 98)
- Secondary interpreter: Python 3.14.4 (OUT of declared matrix; also the `python3` default on this box)

## Facts

**Failures observed, reported first per instructions:**

1. **`python -m pip install -e .` does not install `pytest`.** `pyproject.toml` declares zero mandatory dependencies and no `test`/`dev` extras that pull in pytest (`llm`, `duckdb`, `yaml`, `tokenizer`, `benchmark`, `all` — none include pytest). As a direct result, on the clean `python3.11` venv built per this preflight: `pytest --collect-only`, `pytest -q`, and the `test_suite` sub-check inside `shiroe release check` all fail/degrade with `No module named pytest`. This is a **preflight-script gap, not a repo defect**: actual CI (`.github/workflows/shr-verify.yml`) installs pytest explicitly — `pip install -e . pytest` (line 215) and `python3 -m pip install pytest coverage` (line 112) — steps this preflight script does not include.
2. **The secondary interpreter pass is not a fair comparison because of #1.** `python3.14` was run with no venv and no `pip install -e .` at all (per instructions). It happened to have `pytest 9.1.1` already installed system-wide, and `import shiroe` succeeded anyway because `python -m pytest` / `python -m shiroe` add the current working directory (the repo root) to `sys.path`, making the in-tree `shiroe/` package importable without any install step. Net effect: `python3.14 -m pytest -q` and `python3.14 -m shiroe release check` both **pass** (978 passed, 1 skipped) while the equivalent `python3.11` commands **fail** — purely an environment/tooling artifact (pytest present vs. absent), not a behavioral difference in the code under either interpreter.
3. **Running the test suite mutates a tracked file and does not restore it.** `tests/test_benchmark_suite.py::test_run_all_is_idempotent` shells out to `benchmarks/run-all.py` twice as a subprocess. That script rewrites `benchmarks/results.json` **and** `docs/BENCHMARK_REPORT.md` (the latter's `_Generated: <date>._` line) on every invocation. The test restores `benchmarks/results.json` from a saved snapshot in its `finally` block but has no equivalent restore for `docs/BENCHMARK_REPORT.md`. Consequence observed live during this baseline run: after `python3.14 -m pytest` completed green, `git status --short` showed `M docs/BENCHMARK_REPORT.md` (only the `_Generated:` date line changed, e.g. `2026-08-01` → `2026-08-03`). Per this task's mandate not to modify any existing file, that change was reverted with `git checkout -- docs/BENCHMARK_REPORT.md` before finishing; `git status --short` is clean at the end of this run (only `docs/canon/SHIROE_BASELINE.md` is new). **Any CI gate that asserts a clean tree after running the full test suite will fail non-deterministically depending on the date the job runs.**
4. **The instructed `pytest -q` invocation prints no final summary line.** `pytest.ini` already sets `addopts = -q --strict-markers`. The preflight script's own `-q` on the command line stacks with that, raising quiet-level to `-qq`, which suppresses pytest's final `"N passed in Ys"` line — output ends at a bare `[100%]` with nothing after it. Confirmed by re-running the identical command without the extra `-q`: `978 passed, 1 skipped in 16.49s`. This does not change any exit code, only what's visible in the captured log.
5. `shiroe release check` was run **without** `--strict` per the task note (that flag does not exist on `release check`; only `--format {text,md,json}` is accepted). Confirmed no error from omitting it.
6. `git fetch` was **not run** (network mutation, explicitly out of scope for this agent).

## Git state

```
$ git rev-parse --show-toplevel
<repo>

$ git status --short
(clean)

$ git branch --show-current
audit/shr-baseline-evidence

$ git rev-parse HEAD
a4549e06d3a4b398fb2476039026eda49501176a

$ git remote -v
origin	https://github.com/kanadhiayash/shiroe.git (fetch)
origin	https://github.com/kanadhiayash/shiroe.git (push)

$ git branch -a
* audit/shr-baseline-evidence
  chore/shiroe__deep-migration
  chore/shiroe__identity-manifest
  chore/shiroe__readme-assets
  claude/zeref-v3-hardening-execution-837d8f
  dev
  docs/shiroe__brand-assets
  docs/shiroe__brand-surfaces
  docs/shiroe__readme-rewrite
  docs/shiroe__v3-changelog
  fix/shiroe__gate-tightening
  fix/shiroe__retrieval-bm25
  fix/shiroe__stale-db-path-strings
  refactor/shiroe__namespace-rename
  release/shiroe__v3.0.0-alpha.1
  verify-dev
  verify-final
  remotes/origin/HEAD -> origin/main
  remotes/origin/main

$ git tag --sort=-version:refname | head -20
v2.0.0-alpha.1
v1.1.1
v1.1.0
```

Note: `git fetch` was not run, so `remotes/origin/*` and the tag list above reflect this worktree's last-known state, not necessarily current `origin`.

## Environment

```
$ uname -a
Darwin Yashs-MacBook-Air.local 25.3.0 Darwin Kernel Version 25.3.0: Wed Jan 28 20:54:55 PST 2026; root:xnu-12377.91.3~2/RELEASE_ARM64_T8132 arm64

$ sw_vers
ProductName:		macOS
ProductVersion:		26.3.1
ProductVersionExtra:	(a)
BuildVersion:		25D771280a

$ which python3.11 python3.14 python3
<home>/.local/bin/python3.11
/Library/Frameworks/Python.framework/Versions/3.14/bin/python3.14
/Library/Frameworks/Python.framework/Versions/3.14/bin/python3

$ python3.11 --version
Python 3.11.15

$ python3 --version   (== python3.14 on this box)
Python 3.14.4
```

`.venv/` was built with `python3.11 -m venv .venv` (gitignored) and left in place after this run for reuse by a later step, per instructions.

Post-install package list inside `.venv` (`python -m pip list`):
```
Package    Version Editable project location
---------- ------- -----------------------------------------------------------------------------------
pip        26.2
setuptools 79.0.1
shiroe     3.0.0a1 <repo>
```
No `pytest` entry — see Facts #1.

System `python3.14` has `pytest 9.1.1` pre-installed independently of this repo (`python3.14 -m pip show pytest`); `shiroe` is not `pip`-installed for `python3.14` at all — it resolves via `import shiroe` → `.../shiroe/__init__.py` purely because the repo root is `cwd`.

## Preflight results (python3.11, in `.venv`)

| Command | Exit | Result |
|---|---:|---|
| `python3.11 -m venv .venv` | 0 | venv created |
| `python -m pip install --upgrade pip` | 0 | pip 24.0 → 26.2 |
| `python -m pip install -e .` | 0 | `shiroe 3.0.0a1` installed editable; no pytest (not a dependency) |
| `python -m pytest --collect-only -q` | 1 | `No module named pytest` |
| `python -m pytest -q` | 1 | `No module named pytest` |
| `python scripts/shiroe-validate.py` | 0 | Validation passed (all 15/15, 6/6, 8/8, 9/9, 5/5, 3/3, 6/6, 3/3 surfaces OK; 1 warning: empty memory/ scaffold) |
| `python scripts/check-version-consistency.py` | 0 | All surfaces aligned on `3.0.0-alpha.1` |
| `python -m shiroe audit-privacy --strict --fail-classes credentials` | 0 | 0 hits in zero-tolerance class `credentials`; 101 informational hits in non-blocking classes (245 files scanned, 61 allowlisted) |
| `python -m shiroe release check` | 1 | 13 PASS, 1 SKIP (benchmarks — missing local-only fixture), 1 WARN (stale target_profile), **1 FAIL: `test_suite` — pytest exit 1, `No module named pytest`** |

### Verbatim output

```
$ python3.11 -m venv .venv
(no output, exit 0)
```

```
$ python -m pip install --upgrade pip
Requirement already satisfied: pip in ./.venv/lib/python3.11/site-packages (24.0)
Collecting pip
  Downloading pip-26.2-py3-none-any.whl.metadata (4.6 kB)
Downloading pip-26.2-py3-none-any.whl (1.8 MB)
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 1.8/1.8 MB 3.9 MB/s eta 0:00:00
Installing collected packages: pip
  Attempting uninstall: pip
    Found existing installation: pip 24.0
    Uninstalling pip-24.0:
      Successfully uninstalled pip-24.0
Successfully installed pip-26.2
```

```
$ python -m pip install -e .
Obtaining file://<repo>
  Installing build dependencies: started
  Installing build dependencies: finished with status 'done'
  Checking if build backend supports build_editable: started
  Checking if build backend supports build_editable: finished with status 'done'
  Getting requirements to build editable: started
  Getting requirements to build editable: finished with status 'done'
  Preparing editable metadata (pyproject.toml): started
  Preparing editable metadata (pyproject.toml): finished with status 'done'
Building wheels for collected packages: shiroe
  Building editable for shiroe (pyproject.toml): started
  Building editable for shiroe (pyproject.toml): finished with status 'done'
  Created wheel for shiroe: filename=shiroe-3.0.0a1-0.editable-py3-none-any.whl size=11328 sha256=b1394a293bc67620ecdb9f20243d12db6f1a9df4eec7ced59375ea8a574aa239
  Stored in directory: /private/var/folders/ct/52pzrl4s3dv94517ryg4nl180000gn/T/pip-ephem-wheel-cache-ph22bv96/wheels/cf/74/cd/35fc2be6eba5aa12da09fd6a9183dcebddd348a74cb9812486
Successfully built shiroe
Installing collected packages: shiroe
Successfully installed shiroe-3.0.0a1
```

```
$ python -m pytest --collect-only -q
<repo>/.venv/bin/python: No module named pytest
exit=1
```

```
$ python -m pytest -q
<repo>/.venv/bin/python: No module named pytest
exit=1
```

```
$ python scripts/shiroe-validate.py
Shiroe validator — <repo>
Skills:           15/15 (from shiroe-registry.json)
Agents:           6/6 (filesystem vs registry)
Commands:         8/8 (filesystem vs registry)
Team packs:       9/9 (filesystem vs registry)
Config:           5/5
Root privacy:     3/3 (PRIVACY, REDACT, SHARING_POLICY)
v4x canon:        6/6
Harness stubs:    3/3
Memory layout:    flat
PATTERNS lint:    0 finding(s)
Registry schema:  valid (registry/shiroe-registry.schema.json)

Warnings:
  ! memory/ is empty scaffold — run `python3 -m shiroe init` in your project to populate

✔ Validation passed
exit=0
```

```
$ python scripts/check-version-consistency.py
canonical version (from shiroe/VERSION): 3.0.0-alpha.1
  [OK] pyproject.toml:[project].version: '3.0.0-alpha.1'
  [OK] shiroe/__init__.py loader: '3.0.0-alpha.1'
  [OK] shiroe-registry.json:.version: '3.0.0-alpha.1'
  [OK] .claude-plugin/plugin.json:.version: '3.0.0-alpha.1'
  [OK] docs/wiki/Installation.md: '3.0.0-alpha.1'

canonical identity (from shiroe/IDENTITY.json): distribution='shiroe'
  [OK] pyproject.toml:[project].name: 'shiroe'
  [OK] pyproject.toml:[project.scripts].shiroe: 'shiroe.cli:main'
  [OK] pyproject.toml:[project.urls].Homepage: 'https://github.com/kanadhiayash/shiroe'
  [OK] .claude-plugin/plugin.json:.name: 'shiroe'
  [OK] .claude-plugin/marketplace.json:.name: 'shiroe'
  [OK] .claude-plugin/marketplace.json:.plugins[0].name: 'shiroe'
  [OK] shiroe-registry.json exists: 'True'
  [OK] CODEOWNERS exists: 'True'

Tag '2.0.0-alpha.1' < VERSION '3.0.0-alpha.1' — pre-tag state (VERSION bumped, tag pending).

All surfaces aligned on 3.0.0-alpha.1
exit=0
```

```
$ python -m shiroe audit-privacy --strict --fail-classes credentials
Scanning <repo> …  (REDACT.md: <repo>/REDACT.md, strict=True)

Files scanned:  245
Total PII hits: 101
Allowlisted:    61

Hits by class:
  [pii] 38 file(s)
  [proprietary_code] 17 file(s)
  [financial] 2 file(s)
  [internal_paths] 2 file(s)
  [client_data] 1 file(s)

Affected files:
   11  benchmarks/external/fixtures/helmet/helmet.jsonl
    9  benchmarks/results.json
    4  benchmarks/external/README.md
    3  benchmarks/lineage_common.py
    3  shiroe/adapters/harnesses/kimi_code.py
    3  shiroe/cli_benchmark.py
    2  .github/ISSUE_TEMPLATE/bug_report.md
    2  .github/ISSUE_TEMPLATE/config.yml
    2  CLAUDE.md
    2  SECURITY.md
    2  benchmarks/external/fixtures/convomem/user_evidence/1_evidence/SYNTHETIC_Fixture_Persona.json
    2  benchmarks/external/loaders/longmemeval.py
    2  scripts/fetch-benchmark-data.py
    2  shiroe/adapters/harnesses/__init__.py
    2  shiroe/adapters/harnesses/claude_code.py
    2  shiroe/adapters/harnesses/hermes.py
    2  shiroe/lineage/high.py
    2  shiroe/memory/__init__.py
    2  shiroe/memory/bitemporal.py
    2  shiroe/memory/graph.py
    2  shiroe/memory/schemas.py
    2  shiroe/memory/search.py
    2  shiroe/release/manifest.py
    1  .github/ISSUE_TEMPLATE/security_note.yml
    1  .github/workflows/branch-retention.yml
    1  .github/workflows/shr-verify.yml
    1  benchmarks/adaptivity.py
    1  benchmarks/external/baselines/shiroe_backend.py
    1  benchmarks/loop_control.py
    1  benchmarks/security_containment.py
    1  commands/status.md
    1  commands/team.md
    1  registry/shiroe-registry.schema.json
    1  scripts/check-version-consistency.py
    1  scripts/harness-probe.py
    1  shiroe/adapters/capabilities/generic_skill.py
    1  shiroe/adapters/harnesses/codex.py
    1  shiroe/adapters/harnesses/gemini_cli.py
    1  shiroe/adapters/harnesses/odysseus.py
    1  shiroe/adapters/providers/xai.py
    1  shiroe/capabilities/__init__.py
    1  shiroe/capabilities/lifecycle.py
    1  shiroe/codecs/toon.py
    1  shiroe/core/__init__.py
    1  shiroe/core/errors.py
    1  shiroe/core/reasoning.py
    1  shiroe/env.py
    1  shiroe/lineage/critical.py
    1  shiroe/memory/render.py
    1  shiroe/migrations/__init__.py
    1  shiroe/policy/__init__.py
    1  shiroe/policy/autonomy.py
    1  shiroe/routing/policy.py
    1  shiroe/security/__init__.py
    1  shiroe/storage/__init__.py
    1  shiroe/storage/events.py
    1  shiroe/storage/views.py

✔ 0 hits in zero-tolerance class(es) credentials (101 informational hit(s) in non-blocking classes)
exit=0
```
(Note: absolute repo-root path prefix stripped from the "Affected files" list above for readability; the raw output printed each path in full, e.g. `<repo>/benchmarks/external/fixtures/helmet/helmet.jsonl`.)

```
$ python -m shiroe release check
PASS commit_provenance: HEAD resolved: a4549e06d3a4
FAIL test_suite: pytest exit 1 (<repo>/.venv/bin/python: No module named pytest)
PASS version: shiroe/VERSION exists
PASS memory_layout: tracked memory scaffold present; runtime memory files are generated locally
PASS audit_logs: tracked memory scaffold present; audit logs are generated locally
SKIP benchmarks: suite NOT executed: required lineage intake fixture ZRF_64_repo_lineage_intake.csv is absent (local-only input; WS5). Stored benchmarks/results.json is not accepted as evidence.
PASS factguard: README has no FactGuard findings
PASS evidenceguard: no release-blocking evidence issues
PASS version_consistency: all surfaces + tag lineage aligned
PASS workflow_yaml: 2 workflow(s) parseable
PASS privacy_scan: 0 credentials-class hits; 101 informational hit(s) in non-blocking classes across 57 file(s) (allowlisted: 61)
PASS registry_completeness: registry counts match disk for all 5 surfaces
PASS pyproject_backend: build-backend = setuptools.build_meta
PASS soul_present: SOUL.md present at repo root
WARN target_profiles: 1 profile(s) stale (>60d) but sourced third_party/derived — no authoritative publisher to re-verify against, not treated as a hard failure: gpt-5-5-instant (third_party)
PASS claim_gate: no blocked public-claim patterns found
exit=1
```

## Secondary interpreter (python3.14.4 — out of matrix)

Run without a venv, without any `pip install`, directly against system `python3.14` (which also happens to be this box's default `python3`).

| Command | Exit | Result |
|---|---:|---|
| `python3.14 -m pytest -q` | 0 | 979 items ran; dots to `[100%]`, **no final summary line** (see Facts #4); confirmed via non-`-q` rerun: `978 passed, 1 skipped in 16.49s` |
| `python3.14 scripts/shiroe-validate.py` | 0 | identical output to python3.11 pass |
| `python3.14 scripts/check-version-consistency.py` | 0 | identical output to python3.11 pass |
| `python3.14 -m shiroe release check` | 0 | 14 PASS, 1 SKIP (benchmarks), 1 WARN — **`test_suite` now PASSes** (pytest present system-wide) |

### Difference vs. baseline (python3.11)

`test_suite` and therefore overall `release check` exit code flip from FAIL→PASS between the two interpreter passes. This is **not** a 3.11-vs-3.14 code-behavior difference — it is caused entirely by pytest's availability in each environment (absent in the 3.11 venv built per this preflight script; present system-wide for 3.14 independent of this repo). See Facts #1–#2.

### Verbatim output

```
$ python3.14 -m pytest -q
........................................................................ [  7%]
........................................................................ [ 14%]
........................................................................ [ 22%]
.............................s.......................................... [ 29%]
........................................................................ [ 36%]
........................................................................ [ 44%]
........................................................................ [ 51%]
........................................................................ [ 58%]
........................................................................ [ 66%]
........................................................................ [ 73%]
........................................................................ [ 80%]
........................................................................ [ 88%]
........................................................................ [ 95%]
...........................................                              [100%]
exit=0
```

Supplementary (not one of the mandated commands, run only to explain the missing summary line in the block above — see Facts #4):
```
$ python3.14 -m pytest
[... same dot output ...]
978 passed, 1 skipped in 16.49s
exit=0
```

```
$ python3.14 scripts/shiroe-validate.py
Shiroe validator — <repo>
Skills:           15/15 (from shiroe-registry.json)
Agents:           6/6 (filesystem vs registry)
Commands:         8/8 (filesystem vs registry)
Team packs:       9/9 (filesystem vs registry)
Config:           5/5
Root privacy:     3/3 (PRIVACY, REDACT, SHARING_POLICY)
v4x canon:        6/6
Harness stubs:    3/3
Memory layout:    flat
PATTERNS lint:    0 finding(s)
Registry schema:  valid (registry/shiroe-registry.schema.json)

Warnings:
  ! memory/ is empty scaffold — run `python3 -m shiroe init` in your project to populate

✔ Validation passed
exit=0
```

```
$ python3.14 scripts/check-version-consistency.py
canonical version (from shiroe/VERSION): 3.0.0-alpha.1
  [OK] pyproject.toml:[project].version: '3.0.0-alpha.1'
  [OK] shiroe/__init__.py loader: '3.0.0-alpha.1'
  [OK] shiroe-registry.json:.version: '3.0.0-alpha.1'
  [OK] .claude-plugin/plugin.json:.version: '3.0.0-alpha.1'
  [OK] docs/wiki/Installation.md: '3.0.0-alpha.1'

canonical identity (from shiroe/IDENTITY.json): distribution='shiroe'
  [OK] pyproject.toml:[project].name: 'shiroe'
  [OK] pyproject.toml:[project.scripts].shiroe: 'shiroe.cli:main'
  [OK] pyproject.toml:[project.urls].Homepage: 'https://github.com/kanadhiayash/shiroe'
  [OK] .claude-plugin/plugin.json:.name: 'shiroe'
  [OK] .claude-plugin/marketplace.json:.name: 'shiroe'
  [OK] .claude-plugin/marketplace.json:.plugins[0].name: 'shiroe'
  [OK] shiroe-registry.json exists: 'True'
  [OK] CODEOWNERS exists: 'True'

Tag '2.0.0-alpha.1' < VERSION '3.0.0-alpha.1' — pre-tag state (VERSION bumped, tag pending).

All surfaces aligned on 3.0.0-alpha.1
exit=0
```

```
$ python3.14 -m shiroe release check
PASS commit_provenance: HEAD resolved: a4549e06d3a4
PASS test_suite: pytest executed live: ...........................................                              [100%]
PASS version: shiroe/VERSION exists
PASS memory_layout: tracked memory scaffold present; runtime memory files are generated locally
PASS audit_logs: tracked memory scaffold present; audit logs are generated locally
SKIP benchmarks: suite NOT executed: required lineage intake fixture ZRF_64_repo_lineage_intake.csv is absent (local-only input; WS5). Stored benchmarks/results.json is not accepted as evidence.
PASS factguard: README has no FactGuard findings
PASS evidenceguard: no release-blocking evidence issues
PASS version_consistency: all surfaces + tag lineage aligned
PASS workflow_yaml: 2 workflow(s) parseable
PASS privacy_scan: 0 credentials-class hits; 101 informational hit(s) in non-blocking classes across 57 file(s) (allowlisted: 61)
PASS registry_completeness: registry counts match disk for all 5 surfaces
PASS pyproject_backend: build-backend = setuptools.build_meta
PASS soul_present: SOUL.md present at repo root
WARN target_profiles: 1 profile(s) stale (>60d) but sourced third_party/derived — no authoritative publisher to re-verify against, not treated as a hard failure: gpt-5-5-instant (third_party)
PASS claim_gate: no blocked public-claim patterns found
exit=0
```

## Assumptions

- `python3.11` on this box resolves to `<home>/.local/bin/python3.11`, version 3.11.15.
- `python3.14` resolves to `/Library/Frameworks/Python.framework/Versions/3.14/bin/python3.14`, version 3.14.4, and is also this box's default `python3`.
- "the declared CI matrix" for the baseline interpreter refers to `.github/workflows/shr-verify.yml`'s `matrix.python-version: ['3.11', '3.12', '3.13']` (confirmed present at lines 24 and 98 of that file at this commit).
- `--strict` is not a valid flag on `shiroe release check` (per task note); omitted, and its absence produced no error, corroborating the note.
- No network mutation occurred: `git fetch` was not run at any point in this session.

## Unknowns

- Whether running the exact CI install step (`pip install -e . pytest` or `pip install pytest coverage`) instead of bare `pip install -e .` would change any result here — not tested, since the task's preflight script specifies only `pip install -e .`.
- Behavior on `python3.12` and `python3.13` (the other two declared CI matrix members) — not tested; only 3.11 (baseline) and 3.14 (secondary/out-of-matrix) were in scope for this run.
- Whether `docs/BENCHMARK_REPORT.md` not being restored by `test_run_all_is_idempotent` (Facts #3) is a known/accepted gap or an oversight — not investigated further; flagged as a risk below.
- Root cause/history of the 101 non-blocking `audit-privacy` hits (`pii`, `proprietary_code`, `financial`, `internal_paths`, `client_data` classes) — not investigated; the zero-tolerance `credentials` class was clean, which is what `--fail-classes credentials` gates on.

## Risks

- **Preflight-script/CI drift**: this task's preflight installs only `pip install -e .`, while actual CI installs `pytest` (and `coverage`) as a separate, explicit step. Any process that treats this preflight script as equivalent to CI will see false FAILs on `pytest` and `shiroe release check` that CI itself would not produce.
- **Non-deterministic dirty tree after test runs**: `tests/test_benchmark_suite.py::test_run_all_is_idempotent` regenerates `docs/BENCHMARK_REPORT.md`'s `_Generated: <date>._` line via `benchmarks/run-all.py` but only restores `benchmarks/results.json` afterward, not the report file. A CI step asserting a clean working tree after `pytest` would intermittently fail depending on the run date, even though the test itself passes. Not fixed here per instructions not to repair the repo.
- **Environment-dependent gate outcome**: `shiroe release check`'s `test_suite` sub-check shells out to `pytest` and reports PASS/FAIL based on whether the *invoking* Python has pytest importable — with no dependency pinning or bundled pytest, the same commit can legitimately show FAIL (clean 3.11 venv, per this preflight) or PASS (ambient 3.14 with system pytest) purely based on interpreter/environment state, not code correctness.
- 101 informational-class `audit-privacy` hits across 57 files exist today but do not block `release check` (non-zero-tolerance classes); worth a future pass to confirm the allowlist (`REDACT.md`) intent still matches.
- `benchmarks` sub-check is permanently SKIP-only locally (missing `ZRF_64_repo_lineage_intake.csv`, described as a local-only WS5 input) — `benchmarks/results.json` is explicitly not accepted as evidence by the tool itself, so no benchmark claim in this repo is release-gate-verified from this machine.
