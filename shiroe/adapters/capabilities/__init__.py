"""Capability adapters + probing (vNext PR 5, master plan §12).

An adapter is the runtime bridge between an approved capability and Zeref's
executor. Every adapter reports:

- ``enforcement_level`` — how much control Zeref actually has:
  ``A`` embedded (native hooks / subprocess we own),
  ``B`` sidecar/proxy (routed through our CLI or MCP),
  ``C`` context-only (we can only assemble the prompt).
- ``supported_types`` — which capability manifest ``type`` values it handles.
- ``invoke(...)`` — the actual call. Never bypasses ``shiroe.policy`` or
  ``shiroe.capabilities.assert_executable``.
- ``health()`` / ``probe(...)`` — a fast reachability check that writes an
  ``adapter_status`` row (SQLite v2 table, landed in PR 2).

Silent substitution is prohibited. When an adapter fails, the caller sees
the failure — the supervisor (PR 8) decides whether to substitute, and any
substitution is recorded in ``team_assignments`` (PR 7).
"""

from shiroe.adapters.capabilities.base import (
    AdapterResult,
    CapabilityAdapter,
    EnforcementLevel,
    HealthReport,
)
from shiroe.adapters.capabilities.registry import (
    AdapterNotFoundError,
    list_adapters,
    resolve_adapter,
)
from shiroe.adapters.capabilities.health import probe, record_status

__all__ = [
    "AdapterResult", "CapabilityAdapter", "EnforcementLevel", "HealthReport",
    "AdapterNotFoundError", "list_adapters", "resolve_adapter",
    "probe", "record_status",
]
