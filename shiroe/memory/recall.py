"""Recall and explain-search response formatting."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from shiroe.memory.search import search_atoms


def recall(
    root: Path | str,
    query: str,
    *,
    limit: int = 5,
    atom_type: str | None = None,
    status: str | None = "active",
) -> dict[str, Any]:
    result = search_atoms(root, query, limit=limit, atom_type=atom_type, status=status)
    matches = result["matches"]
    top = matches[0]["atom"] if matches else None
    contradictions = [
        match["atom"] for match in search_atoms(
            root,
            query,
            limit=limit,
            atom_type="contradiction",
            status="active",
        )["matches"]
    ]
    contradictions.extend(_detect_live_conflicts(matches, contradictions))
    return {
        "query": query,
        "answer": top["summary"] if top else "No matching memory atom found.",
        "matched_atoms": matches,
        "evidence_grade": top["evidence"] if top else "unverified",
        "source": result["source"],
        "open_contradictions": contradictions,
    }


def _detect_live_conflicts(
    matches: list[dict[str, Any]],
    persisted: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Surface structured conflicts among recalled atoms, even before any
    `contradictions scan` has persisted them. Detection only — never resolves.
    """
    from shiroe.memory.contradictions import detect_conflict, suggest_winner

    known_pairs = set()
    for atom in persisted:
        linked = sorted(
            str(link.get("target_id"))
            for link in atom.get("links", [])
            if isinstance(link, dict) and link.get("target_id")
        )
        if len(linked) == 2:
            known_pairs.add(tuple(linked))

    detected: list[dict[str, Any]] = []
    atoms = [match["atom"] for match in matches if match["atom"].get("type") != "contradiction"]
    for index, left in enumerate(atoms):
        for right in atoms[index + 1:]:
            pair = tuple(sorted((left["id"], right["id"])))
            if pair in known_pairs:
                continue
            conflict = detect_conflict(left, right)
            if conflict is None:
                continue
            winner = suggest_winner(left, right)
            detected.append({
                "id": f"detected:{pair[0]}:{pair[1]}",
                "type": "contradiction",
                "status": "active",
                "persisted": False,
                "claim": f"Contradiction between {left['id']} and {right['id']}",
                "summary": (
                    f"{left['claim']} <> {right['claim']} | {conflict['reason']} | "
                    + (f"suggested_winner={winner} (higher evidence grade)" if winner
                       else "suggested_winner=none (equal evidence grades)")
                    + "; human arbitration required — run `shiroe contradictions scan` to persist"
                ),
                "left_id": left["id"],
                "right_id": right["id"],
                "suggested_winner": winner,
            })
            known_pairs.add(pair)
    return detected


def explain_search(
    root: Path | str,
    query: str,
    *,
    limit: int = 3,
    atom_type: str | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    result = search_atoms(root, query, limit=limit, atom_type=atom_type, status=status)
    return {
        "query": query,
        "tokens": result["tokens"],
        "source": result["source"],
        "candidates": [
            {
                "id": match["atom"]["id"],
                "type": match["atom"]["type"],
                "status": match["atom"]["status"],
                "score": match["score"],
                "why_selected": match["why"],
                "claim": match["atom"]["claim"],
                "evidence": match["atom"]["evidence"],
            }
            for match in result["matches"]
        ],
    }
