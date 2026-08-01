"""Handoff success axis."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from benchmarks.helpers import add_atom, axis_result, print_json_result, temp_memory_root
from shiroe.handoff.compiler import compile_handoff


def run() -> dict:
    with temp_memory_root() as root:
        decision = add_atom(root, atom_type="decision", claim="Keep handoffs source-backed.")
        risk = add_atom(root, atom_type="risk", claim="Do not include private paths in public handoffs.")
        result = compile_handoff(root, target="human", objective="Continue benchmark review.")
        markdown_exists = Path(result["markdown"]).exists()
        json_exists = Path(result["json"]).exists()
        files_ok = markdown_exists and json_exists
        markdown = Path(result["markdown"]).read_text(encoding="utf-8")
        data = json.loads(Path(result["json"]).read_text(encoding="utf-8"))

    content_ok = decision["id"] in markdown and risk["id"] in markdown
    json_ok = data["target"] == "human" and data["active_decisions"] and data["open_risks"]
    checklist_ok = "python3 -m pytest -q" in data["verification_checklist"]
    return axis_result("handoff_success", {
        "artifact_files": (10.0 if files_ok else 0.0, f"markdown_exists={markdown_exists} json_exists={json_exists}"),
        "source_backed_content": (10.0 if content_ok else 0.0, "atom ids present in markdown"),
        "machine_readable_json": (10.0 if json_ok else 0.0, f"target={data.get('target')}"),
        "verification_checklist": (10.0 if checklist_ok else 0.0, "checklist present"),
    })


if __name__ == "__main__":
    sys.exit(print_json_result(run()))
