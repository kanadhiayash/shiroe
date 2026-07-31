---
name: ship
agents: 3
max_agents: 4
read_only: false
description: Changelog drafter + Release reviewer + Deploy verifier. For release preparation.
output_dir: team/
---

# ship team pack

> Sourced from SHIROE_OS §8.

## Roster

| Role | Responsibility |
|---|---|
| **Changelog drafter** | Reads commits / PRs since last release; drafts `team/ship-changelog.md` and `CHANGELOG.md` entry. |
| **Release reviewer** | Verifies version bumps, migration notes, breaking-change call-outs, deprecation timelines. Writes `team/ship-review.md`. |
| **Deploy verifier** | Runs the deploy checklist (smoke tests, health checks, rollback plan, monitoring hooks). Writes `team/ship-verify.md`. |

## When to use

- Tagging a release
- Pushing to staging or prod
- Cutting a hotfix
- Plugin marketplace update

## Activation

`/team ship`

Optional args:
- `--version=<semver>` — target version
- `--dry` — produce all artifacts but do not tag/push

## Outputs

| File | Owner |
|---|---|
| `team/ship-changelog.md` | Changelog drafter (draft for CHANGELOG.md) |
| `team/ship-review.md` | Release reviewer |
| `team/ship-verify.md` | Deploy verifier |

## Rules

- **Deploy verifier blocks** if any checklist item fails. Override requires explicit user approval recorded in `memory/DECISIONS.md`.
- **Breaking changes** must be flagged in `ship-review.md` with migration instructions.
- **Version bumps** follow semver: patch (fix), minor (additive), major (breaking).
- **CHANGELOG.md** is appended to by Changelog drafter only after Release reviewer pass.
- **Pre-deploy** Deploy verifier confirms rollback path exists.

## Hand-off protocol

1. Changelog drafter reads `git log <last-tag>..HEAD`, produces `team/ship-changelog.md`.
2. Release reviewer audits the draft + verifies semver + version bumps + breaking-change notes.
3. On pass: Changelog drafter appends to `CHANGELOG.md`.
4. Deploy verifier runs checklist. Reports go / no-go.
5. On go: user (not agent) executes the tag/push/deploy.
