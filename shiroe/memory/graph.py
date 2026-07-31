"""Derived graph cache built from canonical memory atoms."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from shiroe.lock import MemoryLock, atomic_write
from shiroe.memory.atom_store import AtomStore


GRAPH_PATH = Path("memory") / "indexes" / "derived-graph.json"


def build_derived_graph(root: Path | str = Path(".")) -> dict[str, Any]:
    """Build a derived, rebuildable graph from JSONL atoms.

    Atom JSONL is the v1 append-only history. Under vNext ADR-0001 canonical state lives in memory/state/zeref2.sqlite; this graph is an index/view for traversal and
    provenance checks, never a source of truth.
    """
    root_path = Path(root)
    atoms = AtomStore(root_path).load()
    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []

    for atom in atoms:
        atom_id = str(atom["id"])
        nodes[atom_id] = {
            "id": atom_id,
            "kind": "atom",
            "type": atom["type"],
            "status": atom["status"],
            "evidence": atom["evidence"],
            "source": atom["source"],
        }
        source_id = f"source:{atom['source']}"
        nodes.setdefault(source_id, {"id": source_id, "kind": "source", "source": atom["source"]})
        edges.append({"from": atom_id, "to": source_id, "kind": "sourced_by"})

        for entity in atom.get("entities", []):
            entity_id = f"entity:{entity}"
            nodes.setdefault(entity_id, {"id": entity_id, "kind": "entity", "name": entity})
            edges.append({"from": atom_id, "to": entity_id, "kind": "mentions"})

        for link in atom.get("links", []):
            link_id = f"link:{link}"
            nodes.setdefault(link_id, {"id": link_id, "kind": "link", "target": link})
            edges.append({"from": atom_id, "to": link_id, "kind": "links_to"})

    return {
        "canonical": False,
        "source_of_truth": "memory/l1_atoms/*.jsonl",  # v1 layer; canonical state per ADR-0001 lives in memory/state/zeref2.sqlite
        "node_count": len(nodes),
        "edge_count": len(edges),
        "nodes": sorted(nodes.values(), key=lambda item: item["id"]),
        "edges": sorted(edges, key=lambda item: (item["from"], item["kind"], item["to"])),
    }


def write_derived_graph(root: Path | str = Path(".")) -> dict[str, Any]:
    """Write the derived graph cache under memory/indexes."""
    root_path = Path(root)
    graph = build_derived_graph(root_path)
    path = root_path / GRAPH_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    with MemoryLock(root_path / "memory"):
        atomic_write(path, json.dumps(graph, indent=2, sort_keys=True) + "\n")
    return {**graph, "path": str(path)}
