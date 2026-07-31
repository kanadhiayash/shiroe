"""Prompt classification without external model calls."""

from __future__ import annotations

import re
from typing import Any


STRUCTURED_MARKERS = (
    "objective:",
    "deliverable:",
    "constraints:",
    "success criteria:",
    "verification:",
)
UNSAFE_RE = re.compile(
    r"\b(password|private key|api key|secret key|token|credential)\b",
    re.I,
)
ACTION_RE = re.compile(
    r"\b(add|build|change|fix|update|create|implement|write|review|audit|run|make)\b",
    re.I,
)


def classify_prompt(raw_prompt: str) -> dict[str, Any]:
    text = raw_prompt.strip()
    lowered = text.lower()
    markers = [marker for marker in STRUCTURED_MARKERS if marker in lowered]

    if not text:
        classification = "AMBIGUOUS"
        reason = "empty prompt"
    elif UNSAFE_RE.search(text):
        classification = "UNSAFE"
        reason = "contains sensitive-secret shaped wording"
    elif len(markers) >= 3:
        classification = "STRUCTURED"
        reason = "contains structured task markers"
    elif ACTION_RE.search(text) and _has_context_hint(lowered):
        classification = "SEMI_STRUCTURED"
        reason = "contains action and context hints"
    elif ACTION_RE.search(text):
        classification = "UNSTRUCTURED"
        reason = "contains action but lacks execution details"
    else:
        classification = "AMBIGUOUS"
        reason = "missing clear action"

    return {
        "classification": classification,
        "reason": reason,
        "markers": markers,
        "missing_info": _missing_info(text, classification),
    }


def _has_context_hint(lowered: str) -> bool:
    return any(
        hint in lowered
        for hint in (
            " file",
            " path",
            " screen",
            " page",
            " component",
            " command",
            " test",
            " like ",
            " match ",
            "/",
            ".py",
            ".md",
            ".ts",
            ".tsx",
        )
    )


def _missing_info(text: str, classification: str) -> list[str]:
    lowered = text.lower()
    missing = []
    if classification in {"UNSTRUCTURED", "AMBIGUOUS"}:
        if not _has_context_hint(lowered):
            missing.append("target files or source of truth")
        if "test" not in lowered and "verify" not in lowered:
            missing.append("verification command")
        if "success" not in lowered and "done" not in lowered:
            missing.append("success criteria")
    if classification == "UNSAFE":
        missing.append("safe redacted input")
    return missing
