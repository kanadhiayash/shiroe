# Branching

One trunk, short-lived topic branches, nothing else.

## The model

`main` is the only long-lived branch. It is the default branch, the only branch
`origin` carries, the only branch tags are cut from, and the only branch named
by CI's `push` and `pull_request` triggers
(`.github/workflows/shr-verify.yml`).

There is no second long-lived branch — no integration branch, no staging
branch. Earlier revisions of this repository ran a trunk plus a long-lived
integration branch; that model is retired. It produced the divergence recorded
in issue #151: the same release landed on one of the two branches by squash and
on the other by merge commit, so identical content ended up with two different
histories. One trunk cannot diverge from itself.

Every other branch is a **topic branch**: created from current `main`, carrying
one PR's worth of work, deleted when that PR lands.

## Naming

    <type>/shr-<short-description>

Lowercase, hyphen-separated description. Examples from this repository's own
history:

    audit/shr-baseline-evidence
    ci/shr-main-only-trunk
    fix/shr-canonical-state
    chore/shr-repository-cleanup

Allowed types — the set the program actually uses:

| Type | For |
|---|---|
| `feat` | new capability |
| `fix` | corrected behaviour |
| `refactor` | restructuring with no behaviour change |
| `perf` | measured performance work |
| `docs` | documentation only |
| `test` | tests only |
| `bench` | benchmark harness or corpora |
| `ci` | workflows, gates, automation |
| `chore` | housekeeping, dependencies, cleanup |
| `security` | hardening, privacy, disclosure handling |
| `audit` | evidence-gathering that changes no behaviour |
| `release` | a version-bump branch (see below) |
| `revert` | undoing a landed change |

`release/*` is the one exception to "short-lived". A release branch is named per
`docs/RELEASE_PROCESS.md`, carries the version bump and the release notes, and
is then **frozen**: it receives no further commits after the tag is cut, and it
is retained rather than deleted (`GITHUB_OS.md` §Branch naming). It is a
snapshot, not a maintenance line — fixes go to `main` and ship in the next tag.

Branches created before the rename carry the older `<type>/shiroe__<description>`
and `<type>/<legacy-product-name>__<description>` forms. Those names are history; do not create
new ones.

## Lifetime

A topic branch should live hours to days, not weeks. Concretely:

- Branch from the current tip of `main`. Do not branch from another topic branch.
- Keep it to one reviewable change. If it grows a second, unrelated change, open
  a second branch.
- Rebase on `main` rather than merging `main` into it — a topic branch's history
  should read as a series of your own commits.
- Delete it once its PR lands. GitHub's automatic branch deletion on merge is
  the intended behaviour here, and `.github/workflows/branch-retention.yml`
  deliberately does not fire on topic-branch deletion.

Branches that outlive their PR are the failure mode this model exists to
prevent. A branch nobody has rebased in a month is not a work-in-progress, it is
a fork.

## Merging

- PRs target `main`. There is no other base.
- **Squash and merge.** Each PR lands on `main` as one commit whose subject is a
  Conventional Commit with scope `(shiroe)` and whose body summarises the change.
  Merge commits are what produced the #151 divergence; do not use them.
- The commit that lands must be green: the gates in `CONTRIBUTING.md` §"Required
  local gates" pass locally, and `Shiroe Verify` passes on the PR.
- Force-pushing your own topic branch before review is fine. Force-pushing
  `main` is not, ever.

## Retention

Protected refs — `main` and any `release/*` that is kept as a frozen baseline —
are never deleted. If a name is unsafe, rename it to `archive/<original-name>`.
`.github/workflows/branch-retention.yml` is the tripwire for that policy; it
fires on deletion of a protected ref and on nothing else.

Topic branches are exempt: deleting them on merge is the point.

## Related

- `CONTRIBUTING.md` — contribution workflow and required local gates.
- `GITHUB_OS.md` — commit, tag, and classification conventions.
- `docs/RELEASE_PROCESS.md` — what a release branch has to do before it lands.
