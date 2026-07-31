"""Shared lineage internal-quality-axis helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from benchmarks.helpers import axis_result
from shiroe.lineage.critical import audit_critical
from shiroe.lineage.high import audit_high
from shiroe.lineage.importer import import_lineage
from shiroe.lineage.intake import audit_csv
from shiroe.lineage.reference import audit_reference_only


def lineage_reports() -> dict[str, Any]:
    """Run deterministic local lineage gates once for benchmark axes."""
    return {
        "audit": audit_csv(_csv_path()),
        "import": import_lineage(_csv_path(), sandbox=True, latest_default=True, dry_run=True, resolver=_stub_resolver),
        "critical": audit_critical(_csv_path(), strict=True),
        "high": audit_high(_csv_path(), strict=True),
        "reference": audit_reference_only(_csv_path(), strict=True),
    }


def intake_skip(axis: str) -> dict[str, Any] | None:
    """Return a visible SKIP result when the lineage intake CSV is absent.

    The 64-row intake CSV describes the real lineage program and is NOT
    committed to this repository. Committing a synthetic CSV that satisfies
    the hard-coded expectations (64 rows, 10 critical, 21 high, 19
    reference-only) would let these axes report perfect scores against
    fabricated data. Skipping with an explicit reason is the honest
    behavior (SHR-AUDIT-012): skipped axes are reported in the output and
    never count as passing evidence.

    The reason names the CSV by FILENAME, never by resolved absolute path.
    `run-all.py` writes this string into docs/BENCHMARK_REPORT.md and
    benchmarks/results.json, both tracked in a public repo, so an absolute
    path here commits the operator's home directory (handoff prohibition on
    private absolute paths; REDACT.md `internal_paths`). A filename is also
    machine-independent, which keeps the generated artifacts reproducible
    instead of dirtying the worktree on every developer's machine.
    """
    path = Path(_csv_path())
    if path.exists():
        return None
    return {
        "axis": axis,
        "score": None,
        "skipped": True,
        "reason": (
            f"lineage intake CSV {path.name} not found. The 64-row intake "
            "dataset is local-only and intentionally not committed. Set "
            "ZEREF_LINEAGE_INTAKE_CSV or place the CSV at the repo root to "
            "run this axis. Skipped axes are reported explicitly and do not "
            "count as passing (SHR-AUDIT-012)."
        ),
        "sub": {},
    }


def lineage_axis(axis: str, subs: dict[str, tuple[bool, str]]) -> dict[str, Any]:
    return axis_result(axis, {
        key: (10.0 if passed else 0.0, evidence)
        for key, (passed, evidence) in subs.items()
    })


def _csv_path():
    from shiroe.lineage.importer import default_csv_path

    return default_csv_path()


def _stub_resolver(row):
    """Stub resolver — returns synthesized fixture identities for lineage schema-conformance
    axes. NOT a real GitHub resolver. Every axis backed by this stub reports
    'lineage-schema-conformance' semantics, not empirical GitHub state (see SHR-AUDIT-014)."""
    from shiroe.lineage.importer import SourceIdentity

    if row.source_kind != "github":
        return SourceIdentity(
            repo_url=row.repo_url,
            owner_name=row.repo_name,
            default_branch="",
            commit_sha="",
            archived=False,
            private=False,
            updated_at="",
            license="citation",
            subdirectory=row.subdirectory,
            row_ids=[row.id],
            source_kind="non_github",
            notes=["concept_source"],
        )
    return SourceIdentity(
        repo_url=f"https://github.com/{row.github_repo}",
        owner_name=row.github_repo,
        default_branch="default",
        commit_sha=f"fixture-{row.id:02d}",
        archived=row.github_repo.lower() == "microsoftarchive/promptbench",
        private=False,
        updated_at="fixture",
        license="NOASSERTION",
        subdirectory=row.subdirectory,
        row_ids=[row.id],
        source_kind="github",
        notes=["local_fixture_metadata"],
    )
