"""Prompt rewriting into executable task briefs."""

from __future__ import annotations

import json
import re
from typing import Any

from shiroe.prompt.classify import classify_prompt


def build_brief(raw_prompt: str) -> dict[str, Any]:
    classification = classify_prompt(raw_prompt)
    text = raw_prompt.strip()
    objective = _objective(text)
    context = _context(text)
    brief = {
        "classification": classification["classification"],
        "objective": objective,
        "context": context,
        "constraints": [
            "Read relevant files before editing.",
            "Reuse existing project patterns where possible.",
            "Do not change unrelated behavior.",
        ],
        "deliverable": _deliverable(objective),
        "execution_loop": [
            "Inspect the current implementation.",
            "Inspect the referenced source of truth.",
            "Apply the smallest safe change.",
            "Run focused verification.",
            "Report changed files and results.",
        ],
        "success_criteria": [
            "Requested behavior is implemented with minimal unrelated diff.",
            "Relevant tests or validation commands pass.",
        ],
        "verification": _verification(text),
        "risks": _risks(classification),
        "missing_info": classification["missing_info"],
        "source_prompt": text,
    }
    if classification["classification"] == "UNSAFE":
        brief["deliverable"] = "Blocked until sensitive input is redacted."
        brief["execution_loop"] = ["Ask for redacted input before continuing."]
        brief["success_criteria"] = ["No credentials or secrets are persisted."]
    return brief


def rewrite_prompt(raw_prompt: str) -> dict[str, Any]:
    brief = build_brief(raw_prompt)
    return {
        "classification": brief["classification"],
        "brief": brief,
        "markdown": brief_to_markdown(brief),
    }


def brief_to_markdown(brief: dict[str, Any]) -> str:
    lines = [
        "Objective:",
        brief["objective"],
        "",
        "Context:",
        brief["context"],
        "",
        "Constraints:",
    ]
    lines.extend(f"- {item}" for item in brief["constraints"])
    lines.extend(["", "Deliverable:", brief["deliverable"], "", "Execution loop:"])
    lines.extend(f"{idx}. {item}" for idx, item in enumerate(brief["execution_loop"], 1))
    lines.extend(["", "Success criteria:"])
    lines.extend(f"- {item}" for item in brief["success_criteria"])
    lines.extend(["", "Verification:"])
    lines.extend(f"- {item}" for item in brief["verification"])
    if brief["missing_info"]:
        lines.extend(["", "Missing info:"])
        lines.extend(f"- {item}" for item in brief["missing_info"])
    if brief["risks"]:
        lines.extend(["", "Risks:"])
        lines.extend(f"- {item}" for item in brief["risks"])
    return "\n".join(lines).rstrip() + "\n"


def _objective(text: str) -> str:
    if not text:
        return "Clarify the requested task."
    cleaned = re.sub(r"\s+", " ", text).strip()
    if cleaned.endswith("."):
        return cleaned
    return cleaned + "."


def _context(text: str) -> str:
    lowered = text.lower()
    if "like" in lowered or "match" in lowered:
        return "Use the referenced existing behavior or surface as the source of truth."
    if "/" in text or "." in text:
        return "The prompt includes explicit file, path, command, or artifact references to preserve."
    return "Context is limited to the raw user prompt; missing details are listed below."


def _deliverable(objective: str) -> str:
    return f"Completed task brief for: {objective}"


def _verification(text: str) -> list[str]:
    commands = re.findall(r"`([^`]+)`", text)
    if commands:
        return commands
    lowered = text.lower()
    if "test" in lowered:
        return ["Run the relevant test command named by the project."]
    return ["Run focused validation for the changed surface.", "Report any unverified areas."]


def _risks(classification: dict[str, Any]) -> list[str]:
    if classification["classification"] == "UNSAFE":
        return ["Prompt may contain sensitive material."]
    if classification["missing_info"]:
        return ["Missing context can cause an incomplete implementation."]
    return []


def brief_to_json(brief: dict[str, Any]) -> str:
    return json.dumps(brief, indent=2, sort_keys=True) + "\n"
