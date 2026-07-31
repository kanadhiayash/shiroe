"""Compile privacy-scrubbed handoff artifacts from atoms.

privacy-audit: allow-file "Handoff compiler references example ISO timestamps + provenance fields; no real user data."
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from shiroe.lock import MemoryLock, atomic_write
from shiroe.memory.atom_store import AtomStore
from shiroe.memory.refine import build_health_report
from shiroe.privacy import scrub


TARGETS = {"codex", "claude", "cursor", "github", "human"}

# Privacy classes exported by default. Everything else fails closed:
#   * "private"    — excluded by default; exported only with include_private=True.
#   * "unknown"    — treated exactly like "private" (fail closed): an atom
#                    whose privacy class was never asserted must not leak
#                    just because nobody classified it.
#   * "local-only" — NEVER exported, even with include_private=True; its
#                    contract is that it never leaves this machine.
_EXPORT_DEFAULT = {"public-safe"}
_EXPORT_WITH_PRIVATE = {"public-safe", "private", "unknown"}


def compile_handoff(
    root: Path | str = Path("."),
    *,
    target: str,
    objective: str = "Continue from current Shiroe memory state.",
    include_private: bool = False,
) -> dict[str, Any]:
    """Compile a scrubbed handoff artifact for `target`.

    Atoms are filtered by their `privacy` class before anything is rendered:
    only "public-safe" atoms are exported by default. Passing
    include_private=True additionally exports "private" and "unknown" atoms
    and emits an audit event recording the override; "local-only" atoms are
    never exported under any flag.
    """
    if target not in TARGETS:
        raise ValueError(f"unsupported handoff target: {target}")
    root_path = Path(root)
    all_atoms = AtomStore(root_path).load(status="active")
    atoms, excluded_atoms = _filter_exportable_atoms(all_atoms, include_private=include_private)
    if include_private:
        _log_private_export(root_path, target=target, atoms=atoms)
    health = build_health_report(root_path)
    ts = datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y%m%dT%H%M%SZ")
    basename = f"{target}-{ts}"
    redact_path = root_path / "REDACT.md"
    objective_clean, objective_report = scrub(
        objective,
        redact_path,
        provenance=f"handoff/{target}/objective",
    )
    handoff = _handoff_payload(target, objective_clean, atoms, health, redact_path)
    field_redactions = objective_report.redacted + handoff.pop("_redactions", 0)
    markdown = _render_markdown(handoff)
    json_text = json.dumps(handoff, indent=2, sort_keys=True) + "\n"

    out_dir = root_path / "memory" / "handoffs"
    out_dir.mkdir(parents=True, exist_ok=True)
    md_path = out_dir / f"{basename}.md"
    json_path = out_dir / f"{basename}.json"
    with MemoryLock(root_path / "memory"):
        atomic_write(md_path, markdown)
        atomic_write(json_path, json_text)
    return {
        "target": target,
        "markdown": str(md_path),
        "json": str(json_path),
        "privacy": {
            "field_redactions": field_redactions,
            "include_private": include_private,
            "excluded_atoms": excluded_atoms,
        },
        "summary": handoff["current_state"],
    }


def _filter_exportable_atoms(
    atoms: list[dict[str, Any]],
    *,
    include_private: bool,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Split atoms into (exportable, excluded-count-by-privacy-class).

    Fails closed: an atom with a missing or unrecognized privacy value is
    treated as "unknown" and follows the "private" rules.
    """
    allowed = _EXPORT_WITH_PRIVATE if include_private else _EXPORT_DEFAULT
    exportable: list[dict[str, Any]] = []
    excluded: dict[str, int] = {}
    for atom in atoms:
        privacy = atom.get("privacy", "unknown")
        if privacy not in ("public-safe", "private", "local-only", "unknown"):
            privacy = "unknown"
        if privacy in allowed:
            exportable.append(atom)
        else:
            excluded[privacy] = excluded.get(privacy, 0) + 1
    return exportable, excluded


def _log_private_export(root_path: Path, *, target: str, atoms: list[dict[str, Any]]) -> None:
    """Record an include_private override in the redaction audit log.

    The event is emitted whenever the override flag is used, so the audit
    trail shows the operator's intent even when no private atom happened to
    exist at the time.
    """
    from shiroe.audit.logger import AuditLogger

    private_ids = [
        atom["id"] for atom in atoms
        if atom.get("privacy", "unknown") in ("private", "unknown")
    ]
    AuditLogger.from_root(root_path).append(
        event_type="redaction",
        status="override",
        reason=f"handoff compiled with include_private=True for target '{target}'",
        guards_run=["handoff_privacy_filter"],
        payload={
            "target": target,
            "private_atoms_included": len(private_ids),
            "private_atom_ids": private_ids,
        },
    )


def _handoff_payload(
    target: str,
    objective: str,
    atoms: list[dict[str, Any]],
    health: dict[str, Any],
    redact_path: Path,
) -> dict[str, Any]:
    by_type: dict[str, list[dict[str, Any]]] = {}
    relevant_files = []
    redactions = 0
    for atom in atoms:
        brief, count = _brief(atom, redact_path)
        redactions += count
        by_type.setdefault(atom["type"], []).append(brief)
        if atom["source_type"] == "file":
            relevant_files.append(brief["source"])
    return {
        "target": target,
        "objective": objective,
        "current_state": {
            "active_atoms": len(atoms),
            "health_passed": health["passed"],
            "open_contradictions": len(health["open_contradictions"]),
        },
        "known_facts": by_type.get("fact", []),
        "active_decisions": by_type.get("decision", []),
        "open_risks": by_type.get("risk", []),
        "open_contradictions": by_type.get("contradiction", []),
        "relevant_files": sorted(set(relevant_files)),
        "do_not_touch": ["legacy memory/*.md unless explicitly rendering views"],
        "next_steps": ["Run recall for targeted context before editing.", "Run focused verification before reporting completion."],
        "verification_checklist": [
            "python3 -m pytest -q",
            "python3 scripts/shiroe-validate.py",
            "python3 -m shiroe.cli --version",
        ],
        "memory_health_summary": health["summary"],
        "_redactions": redactions,
    }


def _brief(atom: dict[str, Any], redact_path: Path) -> tuple[dict[str, Any], int]:
    claim, claim_report = scrub(atom["claim"], redact_path, provenance=f"handoff/atom/{atom['id']}/claim")
    summary, summary_report = scrub(atom["summary"], redact_path, provenance=f"handoff/atom/{atom['id']}/summary")
    source, source_report = scrub(atom["source"], redact_path, provenance=f"handoff/atom/{atom['id']}/source")
    return {
        "id": atom["id"],
        "claim": claim,
        "summary": summary,
        "source": source,
        "source_type": atom["source_type"],
        "evidence": atom["evidence"],
        "status": atom["status"],
    }, claim_report.redacted + summary_report.redacted + source_report.redacted


def _render_markdown(handoff: dict[str, Any]) -> str:
    lines = [
        f"# {handoff['target'].title()} Handoff",
        "",
        "## Objective",
        "",
        handoff["objective"],
        "",
        "## Current State",
        "",
    ]
    for key, value in handoff["current_state"].items():
        lines.append(f"- {key}: {value}")
    sections = [
        ("Known Facts", "known_facts"),
        ("Active Decisions", "active_decisions"),
        ("Open Risks", "open_risks"),
        ("Open Contradictions", "open_contradictions"),
        ("Relevant Files", "relevant_files"),
        ("Do Not Touch", "do_not_touch"),
        ("Next Steps", "next_steps"),
        ("Verification Checklist", "verification_checklist"),
    ]
    for title, key in sections:
        lines.extend(["", f"## {title}", ""])
        items = handoff[key]
        if not items:
            lines.append("- none")
        for item in items:
            if isinstance(item, dict):
                lines.append(
                    f"- {item['claim']} "
                    f"(id: {item['id']}; evidence: {item['evidence']}; source: {item['source']})"
                )
            else:
                lines.append(f"- {item}")
    lines.extend(["", "## Memory Health Summary", ""])
    for key, value in handoff["memory_health_summary"].items():
        lines.append(f"- {key}: {value}")
    return "\n".join(lines).rstrip() + "\n"
