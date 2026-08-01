"""Opt-in implementation registry for high-priority lineage rows."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from shiroe.lineage.importer import default_csv_path
from shiroe.lineage.intake import LineageRow, load_rows


HIGH_IMPLEMENTATIONS: dict[int, dict[str, str]] = {
    4: {"form": "optional-adapter", "boundary": "derived graph cache adapter candidate", "gate": "graph remains rebuildable from atoms"},
    6: {"form": "routing-policy", "boundary": "optional role routing", "gate": "capped team activation only"},
    7: {"form": "handoff-policy", "boundary": "handoff compression", "gate": "compression cannot remove exact constraints"},
    8: {"form": "escalation-policy", "boundary": "council only for high-risk calls", "gate": "no always-on council"},
    10: {"form": "quality-guardrail", "boundary": "public-safe copy gate", "gate": "fact/public-claim scans"},
    16: {"form": "optional-adapter", "boundary": "vector backend candidate", "gate": "stdlib lexical retrieval remains core"},
    21: {"form": "benchmark-fixture", "boundary": "simulation as local tests", "gate": "no runtime dependency"},
    23: {"form": "contract-reference", "boundary": "agent schema reference", "gate": "Shiroe does not become an agent framework"},
    24: {"form": "optional-adapter", "boundary": "Agents SDK adapter target", "gate": "permissioned and opt-in only"},
    25: {"form": "plugin-boundary", "boundary": "skill/plugin contract reference", "gate": "orchestration stays outside core"},
    27: {"form": "routing-policy", "boundary": "risk informed model routing", "gate": "route decisions require evidence"},
    30: {"form": "routing-policy", "boundary": "role packs with caps", "gate": "caps prevent role bloat"},
    31: {"form": "handoff-policy", "boundary": "handoff optimization", "gate": "source-backed compression"},
    32: {"form": "escalation-policy", "boundary": "critical council escalation", "gate": "5.5 High only for final arbitration/security/verdict"},
    33: {"form": "connector-governance", "boundary": "MCP policy shape", "gate": "external writes require approval"},
    34: {"form": "optional-adapter", "boundary": "GitHub connector target", "gate": "audit all external writes"},
    35: {"form": "benchmark-fixture", "boundary": "browser automation fixture", "gate": "outside memory core"},
    41: {"form": "security-fixture", "boundary": "safety eval patterns", "gate": "defensive eval only"},
    46: {"form": "failure-analysis", "boundary": "failure cohort reporting", "gate": "expected/actual/fix/test fields"},
    48: {"form": "benchmark-fixture", "boundary": "adversarial prompt cases", "gate": "fixture-only, archived reference"},
    49: {"form": "benchmark-fixture", "boundary": "simple local eval format", "gate": "stdlib local runner"},
}


def audit_high(csv_path: str | Path | None = None, *, strict: bool = False) -> dict[str, Any]:
    """Audit high-priority lineage rows as opt-in boundaries."""
    path = Path(csv_path) if csv_path else default_csv_path()
    rows = load_rows(path)
    high_rows = [row for row in rows if row.priority == "high"]
    findings = [_finding(row) for row in high_rows]
    issues: list[dict[str, Any]] = []

    expected_ids = set(HIGH_IMPLEMENTATIONS)
    actual_ids = {row.id for row in high_rows}
    if actual_ids != expected_ids:
        issues.append({"kind": "high_id_set", "message": f"expected {sorted(expected_ids)}, got {sorted(actual_ids)}"})
    for finding in findings:
        if not finding["implemented"]:
            issues.append({"kind": "high_missing", "row_id": finding["row_id"], "message": "missing high implementation boundary"})
        if strict and finding["core_dependency"]:
            issues.append({"kind": "core_dependency", "row_id": finding["row_id"], "message": "high rows must stay optional or gated"})

    return {
        "passed": not issues,
        "strict": strict,
        "csv": str(path),
        "counts": {
            "high_rows": len(high_rows),
            "implemented": sum(1 for finding in findings if finding["implemented"]),
            "optional_or_gated": sum(1 for finding in findings if not finding["core_dependency"]),
        },
        "forms": _form_counts(findings),
        "findings": findings,
        "issues": issues,
    }


def _finding(row: LineageRow) -> dict[str, Any]:
    record = HIGH_IMPLEMENTATIONS.get(row.id)
    return {
        "row_id": row.id,
        "repo_name": row.repo_name,
        "github_repo": row.github_repo,
        "implemented": bool(record),
        "form": (record or {}).get("form", ""),
        "boundary": (record or {}).get("boundary", ""),
        "gate": (record or {}).get("gate", ""),
        "core_dependency": False,
        "implementation_route": row.implementation_route,
        "guardrail": row.guardrail,
    }


def _form_counts(findings: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for finding in findings:
        form = finding["form"] or "missing"
        counts[form] = counts.get(form, 0) + 1
    return dict(sorted(counts.items()))
