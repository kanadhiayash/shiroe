"""Agent adapter — reads AGENT.md; delegates to harness or reports C."""

from __future__ import annotations

from pathlib import Path

from shiroe.adapters.capabilities.base import (
    AdapterResult,
    EnforcementLevel,
    HealthReport,
)
from shiroe.capabilities.store import CapabilityStore


class AgentAdapter:
    name = "agent"
    # Without a wired harness adapter we can only assemble context.
    enforcement_level = EnforcementLevel.context_only
    supported_types: tuple[str, ...] = ("agent",)

    def health(self) -> HealthReport:
        return HealthReport(
            adapter=self.name,
            detected_version="1.0",
            enforcement_level=self.enforcement_level,
            supported_features=("agent_md", "context_bundle"),
            healthy=True,
            supported_types=self.supported_types,
        )

    def invoke(self, *, capability_id: str, action: str, inputs: dict,
               permissions: dict | None = None,
               timeout_s: int | None = None) -> AdapterResult:
        root = inputs.get("root")
        if root is None:
            return AdapterResult(
                ok=False, error="missing 'root' input; adapter cannot resolve source",
            )
        store = CapabilityStore(root)
        try:
            row = store.conn.execute(
                "SELECT source_location FROM capability_versions "
                "WHERE capability_id=? ORDER BY created_at DESC LIMIT 1",
                (capability_id,),
            ).fetchone()
        finally:
            store.close()
        if row is None:
            return AdapterResult(
                ok=False, error=f"no version record for {capability_id!r}",
            )
        agent_path = Path(row[0]) / "AGENT.md"
        if not agent_path.exists():
            return AdapterResult(
                ok=False, error=f"AGENT.md missing at {agent_path}",
            )
        text = agent_path.read_text(encoding="utf-8")
        return AdapterResult(
            ok=True, output=text,
            metadata={"enforcement_level": self.enforcement_level.value,
                      "source": str(agent_path),
                      "note": "context-only; a harness adapter must execute"},
        )
