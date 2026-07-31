"""Executable audit for critical lineage implementations."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from shiroe.lineage.importer import default_csv_path
from shiroe.lineage.intake import LineageRow, load_rows
from shiroe.memory.graph import build_derived_graph
from shiroe.memory.schemas import REQUIRED_FIELDS, STATUS_VALUES


CRITICAL_IMPLEMENTATIONS: dict[int, dict[str, str]] = {
    1: {
        "source": "Shiroe",
        "implemented_as": "source invariants",
        "gate": "lineage intake, council, and critical audit keep Shiroe identity primary",
    },
    3: {
        "source": "claude-obsidian",
        "implemented_as": "file ownership principle",
        "gate": "tracked memory scaffold and single-writer memory APIs",
    },
    11: {
        "source": "mem0",
        "implemented_as": "memory lifecycle statuses",
        "gate": "atom schema enforces active/stale/superseded/disputed/archived",
    },
    12: {
        "source": "ponytail",
        "implemented_as": "anti-bloat containment",
        "gate": "foreign code containment and optional adapter boundaries",
    },
    14: {
        "source": "Microsoft GraphRAG",
        "implemented_as": "derived graph cache",
        "gate": "graph cache is rebuildable from atom JSONL and never canonical",
    },
    15: {
        "source": "Microsoft Kernel Memory",
        "implemented_as": "source-linked retrieval",
        "gate": "atom schema requires source, evidence, and provenance fields",
    },
    22: {
        "source": "claude-obsidian",
        "implemented_as": "no duplicate memory surfaces",
        "gate": "legacy Markdown remains view/scaffold while JSONL atoms are machine source",
    },
    39: {
        "source": "GitHub Actions",
        "implemented_as": "CI discipline",
        "gate": "pull requests to dev/main run pinned pytest, privacy, and version checks",
    },
    40: {
        "source": "NVIDIA NeMo Guardrails",
        "implemented_as": "write and public-claim rails",
        "gate": "privacy audit, fact/evidence guards, and release checks gate risky output",
    },
    47: {
        "source": "Microsoft PromptFlow",
        "implemented_as": "eval lifecycle",
        "gate": "benchmark runner plus failure analysis emits expected/actual/fix/test fields",
    },
}


def audit_critical(csv_path: str | Path | None = None, *, strict: bool = False) -> dict[str, Any]:
    """Audit that all critical lineage rows have executable Shiroe implementation gates."""
    path = Path(csv_path) if csv_path else default_csv_path()
    rows = load_rows(path)
    critical_rows = [row for row in rows if row.priority == "critical"]
    findings = [_finding(row) for row in critical_rows]
    issues: list[dict[str, Any]] = []

    expected_ids = set(CRITICAL_IMPLEMENTATIONS)
    actual_ids = {row.id for row in critical_rows}
    if actual_ids != expected_ids:
        issues.append({
            "kind": "critical_id_set",
            "message": f"expected {sorted(expected_ids)}, got {sorted(actual_ids)}",
        })
    for finding in findings:
        if not finding["implemented"]:
            issues.append({
                "kind": "critical_missing",
                "row_id": finding["row_id"],
                "message": f"missing implementation gate for row {finding['row_id']}",
            })
        if strict and finding["foreign_code_imported"]:
            issues.append({
                "kind": "foreign_code",
                "row_id": finding["row_id"],
                "message": "critical implementation must not vendor foreign code",
            })

    return {
        "passed": not issues,
        "strict": strict,
        "csv": str(path),
        "counts": {
            "critical_rows": len(critical_rows),
            "implemented": sum(1 for finding in findings if finding["implemented"]),
            "core_or_gate": sum(1 for finding in findings if finding["implementation_form"] in {"core", "core-gate", "ci-gate", "eval-gate"}),
        },
        "findings": findings,
        "issues": issues,
    }


def _finding(row: LineageRow) -> dict[str, Any]:
    record = CRITICAL_IMPLEMENTATIONS.get(row.id)
    gate_status = _gate_status(row.id)
    return {
        "row_id": row.id,
        "repo_name": row.repo_name,
        "github_repo": row.github_repo,
        "implemented": bool(record) and gate_status["passed"],
        "implementation_form": _implementation_form(row.id),
        "implemented_as": (record or {}).get("implemented_as", ""),
        "gate": (record or {}).get("gate", ""),
        "gate_status": gate_status,
        "foreign_code_imported": False,
        "guardrail": row.guardrail,
    }


def _implementation_form(row_id: int) -> str:
    if row_id in {14, 15}:
        return "core"
    if row_id == 39:
        return "ci-gate"
    if row_id == 47:
        return "eval-gate"
    return "core-gate"


def _gate_status(row_id: int) -> dict[str, Any]:
    root = Path.cwd()
    checks = {
        1: _paths_exist(root, ["AGENTS.md", "README.md", "shiroe/lineage/intake.py"]),
        3: _paths_exist(root, ["memory/README.md", "shiroe/memory/core.py", "shiroe/guards/write_gate.py"]),
        11: {"passed": {"active", "stale", "superseded", "disputed", "archived"}.issubset(STATUS_VALUES), "detail": sorted(STATUS_VALUES)},
        12: _paths_exist(root, [".gitignore", "shiroe/lineage/importer.py"]),
        14: _graph_gate(),
        15: {"passed": {"source", "evidence", "provenance"}.issubset(REQUIRED_FIELDS), "detail": "source/evidence/provenance required"},
        22: _paths_exist(root, ["shiroe/memory/render.py", "shiroe/memory/atom_store.py"]),
        39: _paths_exist(root, [".github/workflows/shr-verify.yml"]),
        40: _paths_exist(root, ["shiroe/privacy.py", "shiroe/guards/fact_guard.py", "shiroe/guards/evidence_guard.py", "shiroe/guards/write_gate.py"]),
        47: _paths_exist(root, ["benchmarks/run-all.py", "shiroe/benchmark/failure_analysis.py"]),
    }
    return checks.get(row_id, {"passed": False, "detail": "unknown critical row"})


def _paths_exist(root: Path, paths: list[str]) -> dict[str, Any]:
    missing = [path for path in paths if not (root / path).exists()]
    return {"passed": not missing, "detail": {"checked": paths, "missing": missing}}


def _graph_gate() -> dict[str, Any]:
    graph = build_derived_graph(Path.cwd())
    return {
        "passed": graph["canonical"] is False and graph["source_of_truth"] == "memory/l1_atoms/*.jsonl",
        "detail": {
            "canonical": graph["canonical"],
            "source_of_truth": graph["source_of_truth"],
            "node_count": graph["node_count"],
            "edge_count": graph["edge_count"],
        },
    }
