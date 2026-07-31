"""CSV intake validation for the 64-source Zeref lineage program."""

from __future__ import annotations

import csv
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


REQUIRED_COLUMNS = [
    "id",
    "section",
    "repo_name",
    "source_link_raw",
    "repo_url",
    "owner",
    "source_type",
    "category",
    "decision_from_lineage",
    "zrf_adoption",
    "priority",
    "council_lens",
    "why_it_matters_to_ZRF",
    "guardrail",
    "implementation_route",
    "next_analysis_question",
]

EXPECTED_TOTAL = 64
EXPECTED_PRIORITY_COUNTS = {"critical": 10, "high": 21}
EXPECTED_REFERENCE_ONLY = 19

GITHUB_RE = re.compile(r"github\.com/([^/\s]+/[^/#?\s]+)")


@dataclass(frozen=True)
class LineageRow:
    """Normalized lineage row from the intake CSV."""

    id: int
    section: str
    repo_name: str
    source_link_raw: str
    repo_url: str
    owner: str
    source_type: str
    category: str
    decision_from_lineage: str
    zrf_adoption: str
    priority: str
    council_lens: str
    why_it_matters_to_zrf: str
    guardrail: str
    implementation_route: str
    next_analysis_question: str
    source_kind: str
    github_repo: str
    subdirectory: str

    @property
    def is_reference_only(self) -> bool:
        return self.zrf_adoption.lower() == "reference only"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "section": self.section,
            "repo_name": self.repo_name,
            "repo_url": self.repo_url,
            "source_type": self.source_type,
            "category": self.category,
            "zrf_adoption": self.zrf_adoption,
            "priority": self.priority,
            "council_lens": self.council_lens,
            "guardrail": self.guardrail,
            "implementation_route": self.implementation_route,
            "source_kind": self.source_kind,
            "github_repo": self.github_repo,
            "subdirectory": self.subdirectory,
        }


def load_rows(csv_path: str | Path) -> list[LineageRow]:
    """Load and normalize lineage rows from a CSV file."""
    path = Path(csv_path)
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        missing = [column for column in REQUIRED_COLUMNS if column not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"missing required columns: {', '.join(missing)}")
        rows = [_normalize_row(raw) for raw in reader]
    return rows


def audit_csv(csv_path: str | Path) -> dict[str, Any]:
    """Return a deterministic validation report for the lineage intake CSV."""
    rows = load_rows(csv_path)
    issues: list[dict[str, Any]] = []
    ids = [row.id for row in rows]
    priorities = Counter(row.priority.lower() for row in rows)
    adoptions = Counter(row.zrf_adoption for row in rows)
    source_kinds = Counter(row.source_kind for row in rows)
    categories = Counter(row.category for row in rows)

    if len(rows) != EXPECTED_TOTAL:
        issues.append(_issue("row_count", f"expected {EXPECTED_TOTAL}, got {len(rows)}"))
    if sorted(ids) != list(range(1, len(rows) + 1)):
        issues.append(_issue("ids", "ids must be contiguous and start at 1"))
    for priority, expected in EXPECTED_PRIORITY_COUNTS.items():
        actual = priorities.get(priority, 0)
        if actual != expected:
            issues.append(_issue("priority_count", f"expected {expected} {priority}, got {actual}"))
    reference_only = sum(1 for row in rows if row.is_reference_only)
    if reference_only != EXPECTED_REFERENCE_ONLY:
        issues.append(_issue("reference_only_count", f"expected {EXPECTED_REFERENCE_ONLY}, got {reference_only}"))

    by_github_repo: dict[str, list[int]] = defaultdict(list)
    for row in rows:
        if not row.repo_url:
            issues.append(_issue("repo_url", "missing repo_url", row.id))
        if not row.guardrail:
            issues.append(_issue("guardrail", "missing guardrail", row.id))
        if not row.implementation_route:
            issues.append(_issue("implementation_route", "missing implementation_route", row.id))
        if row.source_kind == "github" and row.github_repo:
            by_github_repo[row.github_repo.lower()].append(row.id)

    duplicate_sources = {
        repo: row_ids
        for repo, row_ids in sorted(by_github_repo.items())
        if len(row_ids) > 1
    }

    return {
        "passed": not issues,
        "csv": str(Path(csv_path)),
        "expected": {
            "rows": EXPECTED_TOTAL,
            "critical": EXPECTED_PRIORITY_COUNTS["critical"],
            "high": EXPECTED_PRIORITY_COUNTS["high"],
            "reference_only": EXPECTED_REFERENCE_ONLY,
        },
        "counts": {
            "rows": len(rows),
            "priorities": dict(sorted(priorities.items())),
            "adoptions": dict(sorted(adoptions.items())),
            "source_kinds": dict(sorted(source_kinds.items())),
            "categories": dict(sorted(categories.items())),
            "github_sources": source_kinds.get("github", 0),
            "non_github_sources": source_kinds.get("non_github", 0),
        },
        "duplicate_sources": duplicate_sources,
        "rows": [row.to_dict() for row in rows],
        "issues": issues,
    }


def _normalize_row(raw: dict[str, str]) -> LineageRow:
    try:
        row_id = int((raw.get("id") or "").strip())
    except ValueError as exc:
        raise ValueError(f"invalid id: {raw.get('id')!r}") from exc

    repo_url = _clean(raw.get("repo_url"))
    github_repo, subdirectory = _github_identity(repo_url)
    source_kind = "github" if github_repo else "non_github"
    return LineageRow(
        id=row_id,
        section=_clean(raw.get("section")),
        repo_name=_clean(raw.get("repo_name")),
        source_link_raw=_clean(raw.get("source_link_raw")),
        repo_url=repo_url,
        owner=_clean(raw.get("owner")),
        source_type=_clean(raw.get("source_type")),
        category=_clean(raw.get("category")),
        decision_from_lineage=_clean(raw.get("decision_from_lineage")),
        zrf_adoption=_clean(raw.get("zrf_adoption")),
        priority=_clean(raw.get("priority")).lower(),
        council_lens=_clean(raw.get("council_lens")),
        why_it_matters_to_zrf=_clean(raw.get("why_it_matters_to_ZRF")),
        guardrail=_clean(raw.get("guardrail")),
        implementation_route=_clean(raw.get("implementation_route")),
        next_analysis_question=_clean(raw.get("next_analysis_question")),
        source_kind=source_kind,
        github_repo=github_repo,
        subdirectory=subdirectory,
    )


def _github_identity(repo_url: str) -> tuple[str, str]:
    match = GITHUB_RE.search(repo_url)
    if not match:
        return "", ""
    repo = match.group(1).removesuffix(".git")
    parsed = urlparse(repo_url)
    parts = [part for part in parsed.path.strip("/").split("/") if part]
    subdirectory = ""
    if len(parts) > 4 and parts[2] == "tree":
        subdirectory = "/".join(parts[4:])
    return repo, subdirectory


def _clean(value: str | None) -> str:
    return (value or "").strip()


def _issue(kind: str, message: str, row_id: int | None = None) -> dict[str, Any]:
    issue: dict[str, Any] = {"kind": kind, "message": message}
    if row_id is not None:
        issue["row_id"] = row_id
    return issue
