"""Agent-cheap retrieval loop -- Wave 4, item 3 (highest priority).

Grounding: Letta scored 74.0% on LoCoMo using filesystem grep and no vector
database, beating Mem0's 66.9% -- the win came from agent behavior, not
ranking cleverness. Retrieval was cheap enough that the agent called it
repeatedly and refined instead of guessing on the first try. This module
makes that loop affordable in this codebase:

- Terse by default: one line per result (id, type, score, a claim snippet),
  not the full atom. Full detail is opt-in (`full=True`, or detail(id)).
- refine() narrows an existing result set (by type/entity/date) without
  re-tokenizing or re-hitting search_atoms() -- it filters the candidate
  pool `search()` already pulled.
- Atom ids (already globally stable/unique, see schemas.make_atom_id) work
  directly as result references -- no separate id scheme needed.
- Every response says whether it was truncated and why, so an agent knows
  to refine rather than assume it saw everything.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from shiroe.memory.search import search_atoms


# search() pulls this many candidates per query -- more than any sane page
# size, so refine() has a real pool to filter locally instead of having to
# re-query the index for a narrower type/entity/date slice.
CANDIDATE_POOL = 25


class AgentRetrieval:
    """One retrieval loop's worth of session state. Nothing touches disk
    beyond what search_atoms()/AtomStore already do; state here is just the
    last few candidate pools, kept in memory for cheap refine() calls."""

    def __init__(self, root: Path | str):
        self.root = Path(root)
        self._pools: dict[str, list[dict[str, Any]]] = {}
        self._known_atoms: dict[str, dict[str, Any]] = {}
        self._next_id = 1

    def search(
        self,
        query: str,
        *,
        limit: int = 5,
        atom_type: str | None = None,
        status: str | None = "active",
        expand: bool = True,
        full: bool = False,
    ) -> dict[str, Any]:
        """Run a real search and cache the candidate pool under a search_id."""
        result = search_atoms(
            self.root,
            query,
            limit=CANDIDATE_POOL,
            atom_type=atom_type,
            status=status,
            expand=expand,
        )
        search_id = f"s{self._next_id}"
        self._next_id += 1
        self._pools[search_id] = result["matches"]
        for match in result["matches"]:
            self._known_atoms[match["atom"]["id"]] = match["atom"]

        page = self._page(search_id, result["matches"], limit, full)
        page["source"] = result["source"]
        page["abstained"] = result["abstained"]
        page["expansion_terms"] = [entry["term"] for entry in result["expansion"]["added"]]
        if result["abstained"]:
            page["hint"] = "query did not tokenize into any terms; rephrase rather than retry"
        return page

    def refine(
        self,
        search_id: str,
        *,
        atom_type: str | None = None,
        entity: str | None = None,
        since: str | None = None,
        until: str | None = None,
        limit: int = 5,
        full: bool = False,
    ) -> dict[str, Any]:
        """Narrow a previous search's candidate pool. Filters in memory --
        no re-tokenization, no re-hit of the index."""
        pool = self._pools.get(search_id)
        if pool is None:
            return {"error": f"unknown search_id: {search_id}", "hint": "call search() first"}
        filtered = [
            match for match in pool
            if _passes_filters(match["atom"], atom_type, entity, since, until)
        ]
        return self._page(search_id, filtered, limit, full)

    def detail(self, atom_id: str) -> dict[str, Any]:
        """Full atom for a previously-seen id -- cheap if it's still in this
        session's cache, one point lookup otherwise."""
        atom = self._known_atoms.get(atom_id)
        if atom is not None:
            return atom
        from shiroe.memory.atom_store import AtomStore

        found = AtomStore(self.root).get(atom_id)
        return found if found is not None else {"error": f"unknown atom id: {atom_id}"}

    def _page(
        self,
        search_id: str,
        matches: list[dict[str, Any]],
        limit: int,
        full: bool,
    ) -> dict[str, Any]:
        total = len(matches)
        page = matches[:limit]
        truncated = total > limit
        out: dict[str, Any] = {
            "search_id": search_id,
            "total_candidates": total,
            "returned": len(page),
            "truncated": truncated,
            "results": [_terse(match, full) for match in page],
        }
        if total == 0:
            out["hint"] = "no candidates; broaden the query or drop a filter"
        elif truncated:
            out["hint"] = (
                f"{total} candidates, only {len(page)} returned; "
                f"call refine('{search_id}', atom_type=/entity=/since=/until=) to narrow"
            )
        return out


def _terse(match: dict[str, Any], full: bool) -> dict[str, Any]:
    atom = match["atom"]
    if full:
        return {
            "id": atom["id"],
            "score": match["score"],
            "matched_via": match.get("matched_via", "direct"),
            "atom": atom,
        }
    return {
        "id": atom["id"],
        "type": atom["type"],
        "score": match["score"],
        "claim": atom["claim"][:120],
    }


def _passes_filters(
    atom: dict[str, Any],
    atom_type: str | None,
    entity: str | None,
    since: str | None,
    until: str | None,
) -> bool:
    if atom_type and atom.get("type") != atom_type:
        return False
    if entity and not any(entity.lower() in name.lower() for name in _entity_names(atom)):
        return False
    created_at = atom.get("created_at") or ""
    if since and created_at < since:
        return False
    if until and created_at > until:
        return False
    return True


def _entity_names(atom: dict[str, Any]) -> list[str]:
    names = []
    for entity in atom.get("entities", []):
        if isinstance(entity, dict):
            names.append(str(entity.get("name", "")))
        else:
            names.append(str(entity))
    return names
