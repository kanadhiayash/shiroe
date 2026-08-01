"""Deterministic memory health and refinement reports.

privacy-audit: allow-file "Refinement heuristics reference date/PII pattern names as detection specs, not real user data."
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from shiroe.lock import MemoryLock, atomic_write
from shiroe.memory.atom_store import AtomStore
from shiroe.memory.cost_router import audit_budgets


def build_health_report(root: Path | str = Path(".")) -> dict[str, Any]:
    """Build a deterministic health report from atom JSONL and local budgets."""
    root_path = Path(root)
    atoms = AtomStore(root_path).load()
    active_atoms = [atom for atom in atoms if atom["status"] == "active"]
    duplicate_groups = _duplicate_groups(active_atoms)
    report = {
        "summary": {
            "total_atoms": len(atoms),
            "active_atoms": len(active_atoms),
            "duplicate_groups": len(duplicate_groups),
        },
        "active_atoms_by_type": dict(sorted(Counter(atom["type"] for atom in active_atoms).items())),
        "open_contradictions": [
            _brief(atom) for atom in active_atoms if atom["type"] == "contradiction"
        ],
        "stale_atoms": [_brief(atom) for atom in atoms if _is_stale(atom)],
        "unsupported_atoms": [
            _brief(atom)
            for atom in atoms
            if atom["evidence"] in {"F", "unverified"} or not atom["source"].strip()
        ],
        "oversized_views": [
            check for check in audit_budgets(root_path)["checks"] if not check["ok"]
        ],
        "privacy_risks": [
            _brief(atom)
            for atom in atoms
            if atom["privacy"] == "unknown" or "[REDACTED:" in atom["claim"]
        ],
        "orphaned_sources": [_brief(atom) for atom in _orphaned_sources(atoms)],
        "duplicate_atoms": [
            {"claim_key": key, "atoms": [_brief(atom) for atom in group]}
            for key, group in duplicate_groups.items()
        ],
    }
    report["recommended_cleanup"] = _recommendations(report)
    report["passed"] = not any(
        report[key]
        for key in (
            "open_contradictions",
            "stale_atoms",
            "unsupported_atoms",
            "oversized_views",
            "privacy_risks",
            "orphaned_sources",
            "duplicate_atoms",
        )
    )
    return report


def write_health_report(root: Path | str = Path("."), report: dict[str, Any] | None = None) -> dict[str, str]:
    """Write JSON and Markdown health reports under memory/reports/."""
    root_path = Path(root)
    payload = report or build_health_report(root_path)
    reports_dir = root_path / "memory" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    json_path = reports_dir / "memory-health.json"
    md_path = reports_dir / "memory-health.md"
    with MemoryLock(root_path / "memory"):
        atomic_write(json_path, json.dumps(payload, indent=2, sort_keys=True) + "\n")
        atomic_write(md_path, render_health_markdown(payload))
    return {"json": str(json_path), "markdown": str(md_path)}


def refine_memory(
    root: Path | str = Path("."),
    *,
    dry_run: bool = False,
    strict: bool = False,
) -> dict[str, Any]:
    """Produce deterministic cleanup proposals and optional health reports.

    Refinement does not delete atoms and does not resolve contradictions. It
    surfaces safe proposals so a user or explicit command can act later.
    """
    report = build_health_report(root)
    result: dict[str, Any] = {
        "dry_run": dry_run,
        "strict": strict,
        "passed": report["passed"],
        "proposals": _proposals(report),
        "health": report,
        "written": {},
    }
    if not dry_run:
        result["written"] = write_health_report(root, report)
    return result


def render_health_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Memory Health",
        "",
        "## Summary",
        "",
        f"- Total atoms: {report['summary']['total_atoms']}",
        f"- Active atoms: {report['summary']['active_atoms']}",
        f"- Duplicate groups: {report['summary']['duplicate_groups']}",
        f"- Passed: {str(report['passed']).lower()}",
        "",
        "## Active Atoms By Type",
        "",
    ]
    if report["active_atoms_by_type"]:
        for atom_type, count in report["active_atoms_by_type"].items():
            lines.append(f"- {atom_type}: {count}")
    else:
        lines.append("- none")

    sections = [
        ("Open Contradictions", "open_contradictions"),
        ("Stale Atoms", "stale_atoms"),
        ("Unsupported Atoms", "unsupported_atoms"),
        ("Oversized Views", "oversized_views"),
        ("Privacy Risks", "privacy_risks"),
        ("Orphaned Sources", "orphaned_sources"),
        ("Duplicate Atoms", "duplicate_atoms"),
        ("Recommended Cleanup", "recommended_cleanup"),
    ]
    for title, key in sections:
        lines.extend(["", f"## {title}", ""])
        _append_items(lines, report.get(key, []))
    return "\n".join(lines).rstrip() + "\n"


def _append_items(lines: list[str], items: list[Any]) -> None:
    if not items:
        lines.append("- none")
        return
    for item in items:
        if isinstance(item, str):
            lines.append(f"- {item}")
        elif isinstance(item, dict) and "atoms" in item:
            atom_ids = ", ".join(atom["id"] for atom in item["atoms"])
            lines.append(f"- {item['claim_key']}: {atom_ids}")
        elif isinstance(item, dict) and "artifact" in item:
            lines.append(
                f"- {item['artifact']}: {item['estimated_tokens']} tokens "
                f"(budget {item['budget']})"
            )
        elif isinstance(item, dict):
            lines.append(
                f"- {item.get('id', 'unknown')} [{item.get('type', 'unknown')}] "
                f"{item.get('claim', item)}"
            )
        else:
            lines.append(f"- {item}")


def _brief(atom: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": atom["id"],
        "type": atom["type"],
        "claim": atom["claim"],
        "source": atom["source"],
        "evidence": atom["evidence"],
        "status": atom["status"],
    }


def _duplicate_groups(atoms: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for atom in atoms:
        grouped[_claim_key(atom["claim"])].append(atom)
    return {key: group for key, group in grouped.items() if len(group) > 1}


def _claim_key(claim: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", claim.lower())).strip()


def _is_stale(atom: dict[str, Any]) -> bool:
    if atom["status"] == "stale":
        return True
    valid_until = atom.get("valid_until")
    if not valid_until:
        return False
    try:
        expires = datetime.fromisoformat(valid_until.replace("Z", "+00:00"))
    except ValueError:
        return False
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    return expires < datetime.now(timezone.utc)


def _orphaned_sources(atoms: list[dict[str, Any]]) -> list[dict[str, Any]]:
    referenced = set()
    for atom in atoms:
        for link in atom.get("links", []):
            if isinstance(link, dict) and link.get("target_id"):
                referenced.add(link["target_id"])
            elif isinstance(link, str):
                referenced.add(link)
    return [
        atom
        for atom in atoms
        if atom["type"] == "source"
        and atom["status"] == "active"
        and atom["id"] not in referenced
    ]


def _recommendations(report: dict[str, Any]) -> list[str]:
    recommendations = []
    if report["duplicate_atoms"]:
        recommendations.append("Review duplicate atom groups and patch superseded entries explicitly.")
    if report["unsupported_atoms"]:
        recommendations.append("Add source pointers or downgrade unsupported claims before public use.")
    if report["open_contradictions"]:
        recommendations.append("Resolve contradiction cases only with explicit user arbitration.")
    if report["oversized_views"]:
        recommendations.append("Render compact views from atoms instead of rewriting legacy Markdown.")
    if report["privacy_risks"]:
        recommendations.append("Patch unknown privacy atoms after reviewing source sensitivity.")
    if report["orphaned_sources"]:
        recommendations.append("Link source atoms to claim atoms or archive them with an explicit patch.")
    return recommendations or ["No cleanup needed."]


def _proposals(report: dict[str, Any]) -> list[dict[str, Any]]:
    proposals = []
    for group in report["duplicate_atoms"]:
        proposals.append({
            "action": "review-duplicate",
            "atom_ids": [atom["id"] for atom in group["atoms"]],
            "reason": "duplicate normalized claim",
        })
    for atom in report["unsupported_atoms"]:
        proposals.append({
            "action": "add-evidence-or-demote",
            "atom_id": atom["id"],
            "reason": "missing or weak evidence",
        })
    for atom in report["open_contradictions"]:
        proposals.append({
            "action": "arbitrate-contradiction",
            "atom_id": atom["id"],
            "reason": "contradiction cases cannot resolve automatically",
        })
    return proposals
