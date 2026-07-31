"""Prompt rewrite quality axis.

privacy-audit: allow-file "Scorer references example prompt patterns; no user data."
"""

from __future__ import annotations

import sys

from benchmarks.helpers import axis_result, print_json_result
from shiroe.prompt.classify import classify_prompt
from shiroe.prompt.inject import inject_prompt
from shiroe.prompt.rewrite import build_brief, rewrite_prompt


SAMPLE = "I want to change the dashboard screen buttons just like we did on settings page."


def run() -> dict:
    classified = classify_prompt(SAMPLE)
    brief = build_brief(SAMPLE)
    rewritten = rewrite_prompt(SAMPLE)
    injected = inject_prompt(SAMPLE, target="codex")
    unsafe = classify_prompt("Use this secret key fakecredential123")
    fields = {"objective", "context", "constraints", "deliverable", "execution_loop", "success_criteria", "verification", "risks", "missing_info"}
    field_ok = fields.issubset(brief)
    preserve_ok = "settings page" in brief["source_prompt"]
    return axis_result("prompt_rewrite_quality", {
        "classification": (10.0 if classified["classification"] == "SEMI_STRUCTURED" else 5.0, classified["classification"]),
        "brief_fields": (10.0 if field_ok else 5.0, f"fields={sorted(brief)}"),
        "wording_preserved": (10.0 if preserve_ok else 0.0, brief["source_prompt"]),
        "inject_target": (10.0 if "Codex Task Brief" in injected["content"] else 0.0, injected["target"]),
        "unsafe_flag": (10.0 if unsafe["classification"] == "UNSAFE" else 0.0, unsafe["classification"]),
        "markdown_output": (10.0 if "Objective:" in rewritten["markdown"] else 0.0, "markdown generated"),
    })


if __name__ == "__main__":
    sys.exit(print_json_result(run()))
