"""Harness adapter protocol + registry."""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Protocol, runtime_checkable


class HarnessEnforcementLevel(str, Enum):
    embedded = "A"       # native hook, plugin, or subprocess we own
    sidecar = "B"        # routed through CLI / MCP / proxy
    context_only = "C"   # we assemble prompt files; can't guarantee execution


@dataclass(frozen=True)
class HarnessReport:
    name: str
    detected: bool
    detected_version: str | None
    enforcement_level: HarnessEnforcementLevel
    supported_features: tuple[str, ...] = ()
    instruction_files: tuple[str, ...] = ()
    failure_reason: str | None = None


class HarnessNotDetectedError(RuntimeError):
    pass


@runtime_checkable
class HarnessAdapter(Protocol):
    name: str

    def detect(self) -> HarnessReport: ...
    def health(self) -> HarnessReport: ...
    def export_context(self, root: Path, *, objective: str,
                        permissions: dict) -> list[Path]: ...


# Lazy per-adapter imports so each PR (12–18) can land its own file
# without waiting on siblings. Missing adapters raise HarnessNotDetectedError
# rather than an ImportError so downstream code can degrade gracefully.

_LOADERS = {
    "codex": ("shiroe.adapters.harnesses.codex", "CodexAdapter"),
    "claude-code": ("shiroe.adapters.harnesses.claude_code", "ClaudeCodeAdapter"),
    "gemini-cli": ("shiroe.adapters.harnesses.gemini_cli", "GeminiCLIAdapter"),
    "kimi-code": ("shiroe.adapters.harnesses.kimi_code", "KimiCodeAdapter"),
    "hermes": ("shiroe.adapters.harnesses.hermes", "HermesAdapter"),
    "odysseus": ("shiroe.adapters.harnesses.odysseus", "OdysseusAdapter"),
    "grok": ("shiroe.adapters.providers.xai", "GrokContextAdapter"),
}


def resolve_harness(name: str) -> HarnessAdapter:
    if name not in _LOADERS:
        raise KeyError(f"unknown harness {name!r}. Known: {sorted(_LOADERS)}")
    module_name, class_name = _LOADERS[name]
    try:
        mod = __import__(module_name, fromlist=[class_name])
    except ImportError as e:
        raise HarnessNotDetectedError(
            f"harness {name!r} adapter module {module_name!r} not installed: {e}"
        ) from e
    return getattr(mod, class_name)()


def detect_all() -> list[HarnessReport]:
    """Return one HarnessReport per registered harness, whether detected
    or not — honest reporting (§12.4). Adapters whose modules are absent
    surface as detected=False with a clear failure_reason."""
    reports: list[HarnessReport] = []
    for name in _LOADERS:
        try:
            adapter = resolve_harness(name)
            reports.append(adapter.detect())
        except HarnessNotDetectedError as e:
            reports.append(HarnessReport(
                name=name, detected=False, detected_version=None,
                enforcement_level=HarnessEnforcementLevel.context_only,
                failure_reason=str(e),
            ))
    return reports


# ---------------------------------------------------------------------------
# Helpers reused by concrete adapters
# ---------------------------------------------------------------------------

def which(cmd: str) -> str | None:
    return shutil.which(cmd)


def env_hint(*keys: str) -> str | None:
    """Return the first env-var value found for any of the given keys."""
    for k in keys:
        v = os.environ.get(k)
        if v:
            return v
    return None
