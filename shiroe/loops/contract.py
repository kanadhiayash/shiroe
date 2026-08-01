"""Loop contract creation."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from shiroe.core.deprecations import resolve_alias
from shiroe.lock import MemoryLock, atomic_write


def create_loop_contract(
    root: Path | str,
    goal: str,
    *,
    team_pack: str = "lean",
    max_iterations: int = 3,
    verification_method: str = "deterministic simulation",
    memory_mode: str = "observe-only",
) -> dict[str, Any]:
    if max_iterations < 1:
        raise ValueError("max_iterations must be at least 1")
    if memory_mode not in {"observe-only", "document", "learn", "audit"}:
        raise ValueError(f"unsupported memory_mode: {memory_mode}")
    team_pack = resolve_alias(team_pack)
    root_path = Path(root)
    ts = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    loop_id = _loop_id(goal, team_pack, ts)
    contract = {
        "loop_id": loop_id,
        "goal": goal,
        "team_pack": team_pack,
        "allowed_tools": [],
        "budget": {
            "max_iterations": max_iterations,
            "max_model_tier": "mid",
            "max_runtime_minutes": None,
        },
        "success_criteria": ["verification result recorded"],
        "failure_criteria": ["max iterations exceeded", "direct memory mutation requested"],
        "stop_conditions": ["max_iterations", "verification_failed"],
        "verification_method": verification_method,
        "memory_mode": memory_mode,
        "handoff_output": True,
        "created_at": ts,
        "memory_permissions": {
            "direct_memory_write": False,
            "emit_events": True,
            "request_memory_update": True,
        },
    }
    _write_contract(root_path, contract)
    return contract


def _write_contract(root: Path, contract: dict[str, Any]) -> None:
    loop_dir = root / "memory" / "loops" / contract["loop_id"]
    loop_dir.mkdir(parents=True, exist_ok=True)
    latest = root / "memory" / "loops" / "latest.json"
    content = json.dumps(contract, indent=2, sort_keys=True) + "\n"
    with MemoryLock(root / "memory"):
        atomic_write(loop_dir / "contract.json", content)
        atomic_write(latest, content)


def _loop_id(goal: str, team_pack: str, ts: str) -> str:
    digest = hashlib.sha256(f"{goal}|{team_pack}|{ts}".encode("utf-8")).hexdigest()[:12]
    return f"loop_{digest}"
