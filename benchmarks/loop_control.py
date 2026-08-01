"""Loop control axis."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from benchmarks.helpers import axis_result, print_json_result, temp_memory_root
from shiroe.loops.contract import create_loop_contract
from shiroe.loops.runtime import loop_report, loop_status, run_loop


def run() -> dict:
    with temp_memory_root() as root:
        contract = create_loop_contract(root, "Update dashboard buttons", team_pack="small", max_iterations=2)
        result = run_loop(root, "Update dashboard buttons", team_pack="small", max_iterations=2)
        proposal = json.loads(Path(result["memory_update_proposal"]).read_text(encoding="utf-8"))
        status = loop_status(root)
        report = loop_report(root)

    contract_ok = contract["budget"]["max_iterations"] == 2 and contract["memory_permissions"]["direct_memory_write"] is False
    run_ok = result["iterations"] <= 2 and result["verification"]["passed"] is True
    proposal_ok = proposal["direct_memory_write"] is False and proposal["proposed_atoms"] == []
    status_ok = status["verification"]["passed"] is True
    report_ok = report["found"] and "Memory Update Proposal" in report["report"]
    return axis_result("loop_control", {
        "bounded_contract": (10.0 if contract_ok else 0.0, f"max={contract['budget']['max_iterations']}"),
        "run_stops": (10.0 if run_ok else 0.0, f"iterations={result['iterations']}"),
        # Report the two fields proposal_ok actually asserts, not the whole
        # dict: it carries a random loop_id, and this evidence string is
        # written into benchmarks/results.json and docs/BENCHMARK_REPORT.md,
        # both tracked — a fresh id per run dirties the worktree every time.
        "no_direct_memory_write": (
            10.0 if proposal_ok else 0.0,
            f"direct_memory_write={proposal['direct_memory_write']} "
            f"proposed_atoms={len(proposal['proposed_atoms'])}",
        ),
        "status_available": (10.0 if status_ok else 0.0, "latest status read"),
        "report_available": (10.0 if report_ok else 0.0, "report read"),
    })


if __name__ == "__main__":
    sys.exit(print_json_result(run()))
