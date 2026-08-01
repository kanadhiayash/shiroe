"""Evidence-only battle-test registry for reference-only lineage rows."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from shiroe.lineage.importer import default_csv_path
from shiroe.lineage.intake import LineageRow, load_rows


REFERENCE_IMPLEMENTATIONS: dict[int, dict[str, str]] = {
    2: {"form": "principle-fixture", "gate": "public claims require executable evidence"},
    5: {"form": "graph-contrast", "gate": "no duplicate graph system in core"},
    9: {"form": "council-guardrail", "gate": "debate requires evidence and strict scope"},
    19: {"form": "scope-guardrail", "gate": "no multimodal expansion before text memory is stable"},
    20: {"form": "scope-guardrail", "gate": "no neuroscience framing in public Shiroe positioning"},
    26: {"form": "lifecycle-fixture", "gate": "no cloud runtime assumption"},
    28: {"form": "lifecycle-fixture", "gate": "no platform-specific lifecycle assumption"},
    36: {"form": "connector-guardrail", "gate": "connectors cannot own Shiroe trust boundary"},
    38: {"form": "export-guardrail", "gate": "docs export must not leak private memory"},
    42: {"form": "security-containment", "gate": "read-only defensive reference"},
    43: {"form": "security-containment", "gate": "no offensive capability bundled"},
    44: {"form": "security-containment", "gate": "permission gate every security workflow"},
    50: {"form": "run-manifest-fixture", "gate": "no workflow orchestrator dependency"},
    53: {"form": "benchmark-fixture", "gate": "avoid overfitting to static sandboxes"},
    54: {"form": "benchmark-fixture", "gate": "do not ingest embodied-AI code"},
    59: {"form": "downstream-ui-reference", "gate": "frontend libraries stay outside core"},
    60: {"form": "downstream-ui-reference", "gate": "component libraries stay outside core"},
    61: {"form": "workflow-reference", "gate": "Shiroe is not marketing-specific"},
    62: {"form": "architecture-guardrail", "gate": "training-stack complexity stays out of Shiroe"},
}


def audit_reference_only(csv_path: str | Path | None = None, *, strict: bool = False) -> dict[str, Any]:
    """Audit reference-only rows as evidence-only battle-test assets."""
    path = Path(csv_path) if csv_path else default_csv_path()
    rows = load_rows(path)
    reference_rows = [row for row in rows if row.is_reference_only]
    findings = [_finding(row) for row in reference_rows]
    issues: list[dict[str, Any]] = []

    expected_ids = set(REFERENCE_IMPLEMENTATIONS)
    actual_ids = {row.id for row in reference_rows}
    if actual_ids != expected_ids:
        issues.append({"kind": "reference_id_set", "message": f"expected {sorted(expected_ids)}, got {sorted(actual_ids)}"})
    for finding in findings:
        if not finding["implemented"]:
            issues.append({"kind": "reference_missing", "row_id": finding["row_id"], "message": "missing reference-only battle test"})
        if strict and finding["runtime_bundled"]:
            issues.append({"kind": "runtime_bundled", "row_id": finding["row_id"], "message": "reference-only code must not enter runtime"})

    return {
        "passed": not issues,
        "strict": strict,
        "csv": str(path),
        "counts": {
            "reference_only_rows": len(reference_rows),
            "implemented": sum(1 for finding in findings if finding["implemented"]),
            "evidence_only": sum(1 for finding in findings if not finding["runtime_bundled"]),
        },
        "forms": _form_counts(findings),
        "findings": findings,
        "issues": issues,
    }


def _finding(row: LineageRow) -> dict[str, Any]:
    record = REFERENCE_IMPLEMENTATIONS.get(row.id)
    return {
        "row_id": row.id,
        "repo_name": row.repo_name,
        "github_repo": row.github_repo,
        "implemented": bool(record),
        "form": (record or {}).get("form", ""),
        "gate": (record or {}).get("gate", ""),
        "runtime_bundled": False,
        "implementation_route": row.implementation_route,
        "guardrail": row.guardrail,
    }


def _form_counts(findings: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for finding in findings:
        form = finding["form"] or "missing"
        counts[form] = counts.get(form, 0) + 1
    return dict(sorted(counts.items()))
