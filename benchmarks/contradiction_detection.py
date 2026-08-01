"""Contradiction detection axis."""

from __future__ import annotations

import sys

from benchmarks.helpers import add_atom, axis_result, print_json_result, temp_memory_root
from shiroe.memory.atom_store import AtomStore
from shiroe.memory.contradictions import propose_resolution, resolve_contradiction, scan_contradictions


def run() -> dict:
    with temp_memory_root() as root:
        left = add_atom(root, claim="Connector sync is enabled.")
        right = add_atom(root, claim="Connector sync is disabled.", source="benchmark-2")
        scanned = scan_contradictions(root)
        contradiction = scanned["created"][0] if scanned["created"] else {}
        proposed = propose_resolution(root, contradiction["id"]) if contradiction else {}
        before_resolve = AtomStore(root).get(right["id"])
        resolved = resolve_contradiction(root, contradiction["id"], winner=left["id"], reason="benchmark arbitration") if contradiction else {}
        after_resolve = AtomStore(root).get(right["id"])

    created_ok = scanned["count"] == 1 and contradiction.get("type") == "contradiction"
    proposal_ok = "User arbitration required" in proposed.get("proposal", "")
    no_auto_ok = before_resolve and before_resolve["status"] == "active"
    resolve_ok = after_resolve and after_resolve["status"] == "superseded" and resolved.get("winner") == left["id"]
    return axis_result("contradiction_detection", {
        "case_creation": (10.0 if created_ok else 0.0, f"created={scanned['count']}"),
        "arbitration_required": (10.0 if proposal_ok else 0.0, proposed.get("proposal", "missing")),
        "no_silent_resolution": (10.0 if no_auto_ok else 0.0, f"before_status={before_resolve['status'] if before_resolve else 'missing'}"),
        "explicit_resolution": (10.0 if resolve_ok else 0.0, f"after_status={after_resolve['status'] if after_resolve else 'missing'}"),
    })


if __name__ == "__main__":
    sys.exit(print_json_result(run()))
