"""Render human-readable Markdown views from memory atoms."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from shiroe.lock import MemoryLock, atomic_write
from shiroe.memory.atom_store import AtomStore
from shiroe.memory.cost_router import DEFAULT_POLICY, estimate_tokens


VIEW_ALIASES = {
    "hot.md": "hot.md",
    "index.md": "index.md",
    "decisions": "DECISIONS.md",
    "risks": "RISKS.md",
    "contradictions": "CONFLICTS.md",
}


def render_memory_view(root: Path | str, view: str) -> dict[str, Any]:
    """Render one or all supported views under memory/views/."""
    root_path = Path(root)
    if view == "all":
        rendered = [render_memory_view(root_path, name) for name in VIEW_ALIASES]
        return {"view": "all", "rendered": rendered}
    if view not in VIEW_ALIASES:
        raise ValueError(f"unsupported view: {view}")

    atoms = AtomStore(root_path).load()
    filename = VIEW_ALIASES[view]
    content = _render_content(view, atoms)
    views_dir = root_path / "memory" / "views"
    views_dir.mkdir(parents=True, exist_ok=True)
    path = views_dir / filename
    with MemoryLock(root_path / "memory"):
        atomic_write(path, content)
    return {
        "view": view,
        "path": str(path),
        "estimated_tokens": estimate_tokens(content)["estimated_tokens"],
    }


def _render_content(view: str, atoms: list[dict[str, Any]]) -> str:
    active = [atom for atom in atoms if atom["status"] == "active"]
    if view == "hot.md":
        return _render_hot(active)
    if view == "index.md":
        return _render_index(active)
    if view == "decisions":
        return _render_type("Decisions", [atom for atom in active if atom["type"] == "decision"])
    if view == "risks":
        return _render_type("Risks", [atom for atom in active if atom["type"] == "risk"])
    if view == "contradictions":
        return _render_type(
            "Contradictions",
            [atom for atom in active if atom["type"] == "contradiction"],
        )
    raise ValueError(f"unsupported view: {view}")


def _render_hot(atoms: list[dict[str, Any]]) -> str:
    budget = DEFAULT_POLICY["artifact_budgets"]["hot.md"]
    lines = [
        "# memory/views/hot.md",
        "",
        "Generated from active atoms. Legacy memory/hot.md is not modified.",
        "",
    ]
    for atom in sorted(atoms, key=lambda item: item["created_at"], reverse=True):
        candidate = lines + [_atom_line(atom), ""]
        if estimate_tokens("\n".join(candidate))["estimated_tokens"] > budget:
            break
        lines = candidate
    if len(lines) == 4:
        lines.append("- no active atoms")
    return "\n".join(lines).rstrip() + "\n"


def _render_index(atoms: list[dict[str, Any]]) -> str:
    lines = [
        "# memory/views/index.md",
        "",
        "Generated from active atoms. Legacy memory/index.md is not modified.",
        "",
    ]
    by_type: dict[str, list[dict[str, Any]]] = {}
    for atom in atoms:
        by_type.setdefault(atom["type"], []).append(atom)
    if not by_type:
        lines.append("- no active atoms")
    for atom_type in sorted(by_type):
        lines.extend([f"## {atom_type}", ""])
        for atom in sorted(by_type[atom_type], key=lambda item: item["created_at"], reverse=True):
            lines.append(_atom_line(atom))
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _render_type(title: str, atoms: list[dict[str, Any]]) -> str:
    lines = [
        f"# memory/views/{title}",
        "",
        "Generated from active atoms. Legacy Markdown files are not modified.",
        "",
    ]
    if not atoms:
        lines.append("- none")
    for atom in sorted(atoms, key=lambda item: item["created_at"], reverse=True):
        lines.append(_atom_line(atom))
    return "\n".join(lines).rstrip() + "\n"


def _atom_line(atom: dict[str, Any]) -> str:
    tags = ", ".join(atom.get("tags", [])) or "untagged"
    return (
        f"- {atom['claim']} "
        f"(id: {atom['id']}; evidence: {atom['evidence']}; "
        f"source: {atom['source']}; tags: {tags})"
    )
