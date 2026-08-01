"""Adapter registry — resolves ``entrypoint.adapter`` → adapter instance.

Adapters are stateless singletons. Lookup is deterministic and offline.
"""

from __future__ import annotations

from shiroe.adapters.capabilities.base import CapabilityAdapter
from shiroe.adapters.capabilities.agent import AgentAdapter
from shiroe.adapters.capabilities.cli import CLIAdapter
from shiroe.adapters.capabilities.generic_skill import GenericSkillAdapter
from shiroe.adapters.capabilities.mcp_server import MCPServerAdapter
from shiroe.adapters.capabilities.repository_tool import RepositoryToolAdapter


class AdapterNotFoundError(KeyError):
    pass


_ADAPTERS: dict[str, CapabilityAdapter] = {
    "generic": GenericSkillAdapter(),
    "generic-skill": GenericSkillAdapter(),
    "skill": GenericSkillAdapter(),
    "agent": AgentAdapter(),
    "cli": CLIAdapter(),
    "mcp-server": MCPServerAdapter(),
    "mcp_server": MCPServerAdapter(),
    "repository-tool": RepositoryToolAdapter(),
    "repository_tool": RepositoryToolAdapter(),
    # Harness-level aliases for the ``entrypoint.adapter`` values that show
    # up in inferred manifests. All resolve to context-only for now; a
    # future harness adapter package overrides these with real bridges.
    "claude-agent": AgentAdapter(),
    "claude-code": AgentAdapter(),
    "codex": AgentAdapter(),
    "gemini": AgentAdapter(),
}


def resolve_adapter(name: str) -> CapabilityAdapter:
    try:
        return _ADAPTERS[name]
    except KeyError as e:
        raise AdapterNotFoundError(
            f"no capability adapter registered for {name!r}. "
            f"Known: {sorted(set(_ADAPTERS))}"
        ) from e


def list_adapters() -> list[dict]:
    seen: set[str] = set()
    rows: list[dict] = []
    for _, adapter in _ADAPTERS.items():
        if adapter.name in seen:
            continue
        seen.add(adapter.name)
        rows.append({
            "name": adapter.name,
            "enforcement_level": adapter.enforcement_level.value,
            "supported_types": list(adapter.supported_types),
        })
    return rows
