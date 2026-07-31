"""Harness adapters (vNext PRs 12–18, master plan §12).

A harness is the AI-agent runtime the user is actually driving Zeref
through — Claude Code, Codex, Gemini CLI, Kimi Code, Hermes, Odysseus.
Each adapter reports:

- ``name`` / ``detected_version``
- ``enforcement_level`` — A embedded / B sidecar / C context-only
- ``supported_features`` — instructions, hooks, plugins, subagents,
  structured output, MCP, permissions, session import/export,
  model routing
- ``health()`` — same shape as capability adapters
- ``export_context(root, packet)`` — write the harness-specific
  instruction files (AGENTS.md, CLAUDE.md, GEMINI.md, …)

This subpackage only ships the *bridge*; provider model IDs remain in
`shiroe/adapters/providers/*.json`.
"""

from shiroe.adapters.harnesses.base import (
    HarnessAdapter,
    HarnessEnforcementLevel,
    HarnessNotDetectedError,
    HarnessReport,
    detect_all,
    resolve_harness,
)

__all__ = [
    "HarnessAdapter", "HarnessEnforcementLevel", "HarnessNotDetectedError",
    "HarnessReport", "detect_all", "resolve_harness",
]
