"""Runtime enforcement for the documentary policy layer.

At v1.0.0 these policies (PRIVACY.md, REDACT.md, SHARING_POLICY.md,
config/PERMISSIONS.md) were parsed as documentation only. This module
turns them into typed runtime inputs consulted by every network-egress
and LLM-egress code path (see SHR-AUDIT-001, 002, 006, 007, 008).
"""
from shiroe.security.policy import (
    SecurityPolicy,
    NetworkDeniedError,
    ConnectorDisabledError,
    load_policy,
    require_connector,
    require_network,
)

__all__ = [
    "SecurityPolicy",
    "NetworkDeniedError",
    "ConnectorDisabledError",
    "load_policy",
    "require_connector",
    "require_network",
]
