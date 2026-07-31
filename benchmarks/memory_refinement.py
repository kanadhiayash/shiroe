"""Memory refinement axis."""

from __future__ import annotations

import sys

from benchmarks.helpers import add_atom, axis_result, print_json_result, temp_memory_root
from shiroe.memory.refine import build_health_report, refine_memory
from shiroe.memory.render import render_memory_view


def run() -> dict:
    with temp_memory_root() as root:
        add_atom(root, atom_type="decision", claim="Use SQLite FTS before optional vector search.")
        add_atom(root, atom_type="decision", claim="Use SQLite FTS before optional vector search.", source="benchmark-duplicate", evidence="unverified", privacy="unknown")
        health = build_health_report(root)
        dry = refine_memory(root, dry_run=True)
        report_exists_after_dry = (root / "memory" / "reports" / "memory-health.json").exists()
        written = refine_memory(root)
        rendered = render_memory_view(root, "all")

    duplicate_ok = bool(health["duplicate_atoms"])
    unsupported_ok = bool(health["unsupported_atoms"])
    dry_ok = dry["dry_run"] is True and not report_exists_after_dry
    write_ok = bool(written["written"]) and written["proposals"]
    render_ok = rendered["view"] == "all" and len(rendered["rendered"]) >= 5
    return axis_result("memory_refinement", {
        "duplicate_detection": (10.0 if duplicate_ok else 0.0, f"groups={len(health['duplicate_atoms'])}"),
        "unsupported_detection": (10.0 if unsupported_ok else 0.0, f"unsupported={len(health['unsupported_atoms'])}"),
        "dry_run_no_write": (10.0 if dry_ok else 0.0, f"report_after_dry={report_exists_after_dry}"),
        "report_write": (10.0 if write_ok else 0.0, f"json_written={bool(written['written'].get('json'))} markdown_written={bool(written['written'].get('markdown'))}"),
        "view_render": (10.0 if render_ok else 0.0, f"rendered={len(rendered['rendered'])}"),
    })


if __name__ == "__main__":
    sys.exit(print_json_result(run()))
