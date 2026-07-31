"""Compiled team plan dataclass."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SeatAssignment:
    seat_id: str
    capability_id: str
    capability_version_id: str
    score: float
    rationale: dict[str, Any]


@dataclass
class CompiledTeamPlan:
    run_id: str
    task_id: str
    mission_id: str
    policy_id: str
    active_harness: str
    assignments: list[SeatAssignment] = field(default_factory=list)
    execution_graph: list[str] = field(default_factory=list)
    retry_policy: dict = field(default_factory=dict)
    timeout_s: int = 600
    stop_conditions: list[str] = field(default_factory=list)
    verification_required: bool = True
    cost_envelope: dict = field(default_factory=dict)
    memory_scope: str = "project"

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id, "task_id": self.task_id,
            "mission_id": self.mission_id, "policy_id": self.policy_id,
            "active_harness": self.active_harness,
            "assignments": [
                {"seat_id": a.seat_id, "capability_id": a.capability_id,
                 "capability_version_id": a.capability_version_id,
                 "score": a.score, "rationale": a.rationale}
                for a in self.assignments
            ],
            "execution_graph": self.execution_graph,
            "retry_policy": self.retry_policy, "timeout_s": self.timeout_s,
            "stop_conditions": self.stop_conditions,
            "verification_required": self.verification_required,
            "cost_envelope": self.cost_envelope,
            "memory_scope": self.memory_scope,
        }
