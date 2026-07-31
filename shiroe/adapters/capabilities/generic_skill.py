"""Generic skill adapter — reads SKILL.md, provides context only.

A "skill" in the current Zeref repo is markdown-only guidance; there is no
runtime hook that can force the harness to follow it. That's Level C —
we assemble a prompt bundle but we do not execute anything.
"""

from __future__ import annotations

from pathlib import Path

from shiroe.adapters.capabilities.base import (
    AdapterResult,
    EnforcementLevel,
    HealthReport,
)
from shiroe.capabilities.store import CapabilityStore


class GenericSkillAdapter:
    name = "generic-skill"
    enforcement_level = EnforcementLevel.context_only
    supported_types: tuple[str, ...] = ("skill",)

    def health(self) -> HealthReport:
        return HealthReport(
            adapter=self.name,
            detected_version="1.0",
            enforcement_level=self.enforcement_level,
            supported_features=("skill_md", "context_bundle"),
            healthy=True,
            supported_types=self.supported_types,
        )

    def invoke(self, *, capability_id: str, action: str, inputs: dict,
               permissions: dict | None = None,
               timeout_s: int | None = None) -> AdapterResult:
        """Return the SKILL.md content as the "output" — nothing else runs.

        Callers use this to build a context packet; the actual execution
        happens in the harness (Claude Code, Codex, …). We never claim
        Level A/B on this path.
        """
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
        skill_path = Path(row[0]) / "SKILL.md"
        if not skill_path.exists():
            return AdapterResult(
                ok=False, error=f"SKILL.md missing at {skill_path}",
            )
        text = skill_path.read_text(encoding="utf-8")
        return AdapterResult(
            ok=True, output=text,
            metadata={"enforcement_level": self.enforcement_level.value,
                      "source": str(skill_path)},
        )
