"""Compile a mission + policy into a persisted team plan."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from shiroe.capabilities.store import CapabilityStore
from shiroe.execution_policies import get_policy
from shiroe.missions import get_mission
from shiroe.storage import EventEnvelope, EventLog
from shiroe.teams.plan import CompiledTeamPlan, SeatAssignment
from shiroe.teams.resolver import resolve_seat


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def compile_team(
    root: Path | str,
    *,
    task_id: str,
    mission_id: str,
    policy_id: str = "balanced",
    active_harness: str = "claude-code",
) -> CompiledTeamPlan:
    root = Path(root)
    mission = get_mission(root, mission_id)
    policy = get_policy(root, policy_id)

    store = CapabilityStore(root)
    try:
        conn = store.conn

        already_assigned: dict[str, str] = {}
        assignments: list[SeatAssignment] = []
        for seat in mission.required_seats:
            cap, score, rationale = resolve_seat(
                conn, seat, active_harness=active_harness,
                already_assigned=already_assigned,
            )
            already_assigned[seat["id"]] = cap.id
            assignments.append(SeatAssignment(
                seat_id=seat["id"],
                capability_id=cap.id,
                capability_version_id=cap.version_id,
                score=score,
                rationale=rationale,
            ))

        run_id = "run_" + uuid.uuid4().hex[:16]
        now = _now()
        # Upsert mission row so team_runs.mission_id FK holds. Missions live
        # as YAML on disk; the missions table is a run-time registry of
        # blueprints referenced by team_runs.
        conn.execute(
            """
            INSERT OR IGNORE INTO missions (id, name, version, blueprint, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                mission.id, mission.id, mission.version,
                json.dumps({
                    "id": mission.id, "version": mission.version,
                    "required_seats": mission.required_seats,
                    "execution_graph": mission.execution_graph,
                    "required_outputs": mission.required_outputs,
                    "completion": mission.completion,
                }, sort_keys=True),
                now,
            ),
        )
        conn.execute(
            """
            INSERT INTO team_runs
                (id, task_id, mission_id, policy, state,
                 created_at, started_at, ended_at,
                 cost_usd, tokens_input, tokens_output,
                 completion_status, result)
            VALUES (?, ?, ?, ?, 'COMPILED', ?, NULL, NULL,
                    NULL, NULL, NULL, NULL, NULL)
            """,
            (run_id, task_id, mission.id, policy.id, now),
        )
        for a in assignments:
            conn.execute(
                """
                INSERT INTO team_assignments
                    (id, run_id, seat_id, capability_id,
                     capability_version_id, score, rationale)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "ta_" + uuid.uuid4().hex[:16], run_id, a.seat_id,
                    a.capability_id, a.capability_version_id, a.score,
                    json.dumps(a.rationale, sort_keys=True),
                ),
            )
        # Populate execution_steps in mission-graph order.
        step_order = 0
        for step in mission.execution_graph:
            step_order += 1
            conn.execute(
                """
                INSERT INTO execution_steps
                    (id, run_id, step_name, dependency_ids, state,
                     retries, timeout_s, permissions,
                     input_hash, output_hash, started_at, ended_at)
                VALUES (?, ?, ?, ?, 'PENDING', 0, ?, NULL, NULL, NULL, NULL, NULL)
                """,
                (
                    "es_" + uuid.uuid4().hex[:16], run_id, step,
                    json.dumps([
                        s for s in mission.execution_graph
                        if mission.execution_graph.index(s) < step_order - 1
                    ]),
                    600,
                ),
            )
        conn.commit()

        log = EventLog(root, mirror_conn=conn)
        log.append(EventEnvelope(
            event_type="run.compiled",
            actor="team-compiler",
            target=f"run:{run_id}",
            payload={
                "task_id": task_id,
                "mission": mission.id,
                "policy": policy.id,
                "active_harness": active_harness,
                "assignments": [
                    {"seat_id": a.seat_id, "capability_id": a.capability_id,
                     "score": round(a.score, 4)}
                    for a in assignments
                ],
            },
        ))
    finally:
        store.close()

    return CompiledTeamPlan(
        run_id=run_id, task_id=task_id, mission_id=mission.id,
        policy_id=policy.id, active_harness=active_harness,
        assignments=assignments, execution_graph=mission.execution_graph,
        retry_policy={"max_retries": 2, "backoff_s": 1.5},
        timeout_s=policy.cost_envelope.get("tokens_output_max", 600),
        stop_conditions=list(mission.completion.keys()),
        verification_required=policy.independent_verifiers > 0,
        cost_envelope=policy.cost_envelope,
        memory_scope="project",
    )
