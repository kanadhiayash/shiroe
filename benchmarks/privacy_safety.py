"""Privacy safety axis.

privacy-audit: allow-file "Scorer references pattern names + example redact classes; no user data."
"""

from __future__ import annotations

import sys

from benchmarks.helpers import add_atom, axis_result, print_json_result, temp_memory_root
from shiroe.handoff.compiler import compile_handoff
from shiroe.privacy import scrub


def run() -> dict:
    with temp_memory_root() as root:
        clean, report = scrub(
            "secret key fakecredential123 and email person@example.com",
            root / "REDACT.md",
            provenance="benchmark/privacy",
        )
        private_path = "/" + "Users/example/private/project/file.md"
        atom = add_atom(
            root,
            atom_type="decision",
            claim="Use privacy scrub before handoff export.",
            source=private_path,
            source_type="file",
        )
        handoff = compile_handoff(root, target="codex", objective="Continue safely.")
        handoff_text = (root / "memory" / "handoffs").glob("codex-*.md")
        handoff_body = next(handoff_text).read_text(encoding="utf-8")

    credential_ok = "fakecredential123" not in clean and report.redacted >= 2
    handoff_ok = atom["id"] in handoff_body and private_path not in handoff_body
    metadata_ok = handoff["privacy"]["field_redactions"] >= 1
    return axis_result("privacy_safety", {
        "credential_scrub": (10.0 if credential_ok else 0.0, f"redacted={report.redacted}"),
        "handoff_field_scrub": (10.0 if handoff_ok else 0.0, f"atom_id_preserved={atom['id'] in handoff_body}"),
        "redaction_metadata": (10.0 if metadata_ok else 5.0, f"field_redactions={handoff['privacy']['field_redactions']}"),
    })


if __name__ == "__main__":
    sys.exit(print_json_result(run()))
