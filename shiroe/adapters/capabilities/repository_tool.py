"""Repository-tool adapter — run a script that lives in the project repo."""

from __future__ import annotations

from pathlib import Path

from shiroe.adapters.capabilities.base import (
    AdapterResult, EnforcementLevel, HealthReport,
)
from shiroe.adapters.capabilities.cli import CLIAdapter


class RepositoryToolAdapter:
    """Thin wrapper over :class:`CLIAdapter` for tools shipped in the repo.

    The distinction from ``cli`` is provenance-only: repository tools live
    under ``<root>/scripts/`` or an approved capability dir, and are treated
    as Level A because we own the subprocess and can gate it. Everything
    else delegates to the CLI adapter.
    """

    name = "repository-tool"
    enforcement_level = EnforcementLevel.embedded
    supported_types: tuple[str, ...] = ("repository_tool",)

    def __init__(self) -> None:
        self._delegate = CLIAdapter()

    def health(self) -> HealthReport:
        return HealthReport(
            adapter=self.name,
            detected_version="1.0",
            enforcement_level=self.enforcement_level,
            supported_features=("subprocess", "policy_gated", "repo_scope"),
            healthy=True,
            supported_types=self.supported_types,
        )

    def invoke(self, *, capability_id: str, action: str, inputs: dict,
               permissions: dict | None = None,
               timeout_s: int | None = None) -> AdapterResult:
        return self._delegate.invoke(
            capability_id=capability_id, action=action, inputs=inputs,
            permissions=permissions, timeout_s=timeout_s,
        )
