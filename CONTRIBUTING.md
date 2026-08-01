<!-- privacy-audit: allow-file "Contribution doc references example maintainer email + branch names as spec." -->

# Contributing to Shiroe

Shiroe is a local-first AI work control plane for AI-assisted work. Contributions should improve the runtime, docs, guards, benchmarks, install path, or release safety.

## Before starting

For large changes, open an issue first.

For security issues, do not open a public issue. Read `SECURITY.md`.

## Branch naming

Use:

    <type>/shiroe__<short-description>

Allowed types:

- feat
- fix
- refactor
- docs
- test
- ci
- chore
- revert

Examples:

    docs/shiroe__public-surface-overhaul
    fix/shiroe__privacy-redaction-edge-case
    test/shiroe__benchmark-failure-report

## Pull request expectations

A PR should include:

- Summary.
- Why the change is needed.
- User-visible behavior.
- Security impact.
- Benchmark impact.
- Verification commands and outputs.
- Risks and rollback notes.

Keep PRs focused. Prefer several clear commits over one large mixed commit.

## Required local gates

Run before requesting review:

    python3 -m pytest -q
    python3 scripts/shiroe-validate.py
    python3 -m shiroe audit
    python3 -m shiroe audit-privacy --strict
    python3 scripts/check-version-consistency.py
    python3 benchmarks/run-all.py
    git diff --check

For release-facing changes, also run:

    python3 -m shiroe release check

## Public claims

Do not add unsupported claims.

Allowed:

- Local deterministic benchmark gate passed.
- Fixture adapter passed.
- External benchmark verified with named commands and date.

Not allowed without evidence:

- Best.
- World top.
- 10/10 globally.
- Production secure.
- External benchmark leadership.

## Security rules

- Never commit secrets.
- Never weaken privacy gates to pass CI.
- Never publish private paths or credentials.
- Never hide failures in benchmark reports.
- Never claim a workspace was updated unless a file was actually written.
- Never delete release history unless there is a clear security, legal, or public-trust reason.

## Branch retention

Preserve branch history unless removal is required for security or legal reasons. If a branch name is unsafe, rename or archive it rather than deleting history.

## Releases

Release tags use:

    vX.Y.Z

Release notes must include:

- Summary.
- Compatibility.
- Security notes.
- Benchmark scope.
- Known risks.
- Migration notes if needed.

Read `docs/RELEASE_PROCESS.md`.
