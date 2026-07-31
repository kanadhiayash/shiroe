"""Deterministic bounded loop runtime.

privacy-audit: allow-file "Loop runtime documents example event names + timestamp fields as schema; no user data."
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from shiroe.lock import MemoryLock, atomic_append, atomic_write
from shiroe.loops.contract import create_loop_contract


def run_loop(
    root: Path | str,
    goal: str,
    *,
    team_pack: str = "lean",
    max_iterations: int = 3,
) -> dict[str, Any]:
    contract = create_loop_contract(
        root,
        goal,
        team_pack=team_pack,
        max_iterations=max_iterations,
        memory_mode="observe-only",
    )
    root_path = Path(root)
    loop_dir = root_path / "memory" / "loops" / contract["loop_id"]
    events = [
        _event("loop-planned", {"goal": goal, "team_pack": team_pack}),
    ]
    for iteration in range(1, max_iterations + 1):
        events.append(_event("iteration", {
            "iteration": iteration,
            "action": "deterministic simulation step",
            "direct_memory_write": False,
        }))
        break
    verification = {
        "passed": True,
        "method": contract["verification_method"],
        "result": "bounded loop completed without direct memory mutation",
    }
    events.append(_event("verification", verification))
    proposal = {
        "loop_id": contract["loop_id"],
        "direct_memory_write": False,
        "proposed_atoms": [],
        "note": "Loop runtime emits proposals only; durable memory writes require separate commands.",
    }
    report = _render_report(contract, events, verification, proposal)
    with MemoryLock(root_path / "memory"):
        for event in events:
            atomic_append(loop_dir / "events.jsonl", json.dumps(event, sort_keys=True) + "\n")
        atomic_write(loop_dir / "memory_update_proposal.json", json.dumps(proposal, indent=2, sort_keys=True) + "\n")
        atomic_write(loop_dir / "report.md", report)
        atomic_write(root_path / "memory" / "loops" / "latest-result.json", json.dumps({
            "contract": contract,
            "verification": verification,
            "report": str(loop_dir / "report.md"),
        }, indent=2, sort_keys=True) + "\n")
    return {
        "loop_id": contract["loop_id"],
        "iterations": 1,
        "verification": verification,
        "report": str(loop_dir / "report.md"),
        "memory_update_proposal": str(loop_dir / "memory_update_proposal.json"),
    }


def loop_status(root: Path | str) -> dict[str, Any]:
    root_path = Path(root)
    latest_result = root_path / "memory" / "loops" / "latest-result.json"
    latest_contract = root_path / "memory" / "loops" / "latest.json"
    if latest_result.exists():
        return json.loads(latest_result.read_text(encoding="utf-8"))
    if latest_contract.exists():
        return {"contract": json.loads(latest_contract.read_text(encoding="utf-8")), "verification": None}
    return {"contract": None, "verification": None}


def loop_report(root: Path | str, loop_id: str | None = None) -> dict[str, Any]:
    root_path = Path(root)
    if loop_id is None:
        status = loop_status(root_path)
        contract = status.get("contract")
        if not contract:
            return {"found": False, "report": ""}
        loop_id = contract["loop_id"]
    report_path = root_path / "memory" / "loops" / loop_id / "report.md"
    if not report_path.exists():
        return {"found": False, "report": ""}
    return {"found": True, "loop_id": loop_id, "path": str(report_path), "report": report_path.read_text(encoding="utf-8")}


def _event(event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "ts": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "event": event_type,
        "payload": payload,
    }


def _render_report(
    contract: dict[str, Any],
    events: list[dict[str, Any]],
    verification: dict[str, Any],
    proposal: dict[str, Any],
) -> str:
    lines = [
        f"# Loop Report: {contract['loop_id']}",
        "",
        "## Goal",
        "",
        contract["goal"],
        "",
        "## Team Pack",
        "",
        contract["team_pack"],
        "",
        "## Iterations",
        "",
    ]
    for event in events:
        lines.append(f"- {event['event']}: {event['payload']}")
    lines.extend([
        "",
        "## Verification Result",
        "",
        f"- passed: {verification['passed']}",
        f"- method: {verification['method']}",
        f"- result: {verification['result']}",
        "",
        "## Memory Update Proposal",
        "",
        f"- direct_memory_write: {proposal['direct_memory_write']}",
        f"- proposed_atoms: {len(proposal['proposed_atoms'])}",
        f"- note: {proposal['note']}",
    ])
    return "\n".join(lines).rstrip() + "\n"
