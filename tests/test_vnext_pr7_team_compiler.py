"""vNext PR 7 gate tests — team compiler + resolver."""

from __future__ import annotations

import json
import shutil
import sqlite3
import uuid
from pathlib import Path

import pytest

from shiroe.capabilities import (
    approve,
    inspect_source,
    register_discovery,
)
from shiroe.capabilities.discovery import DiscoveredCapability
from shiroe.capabilities.store import CapabilityStore
from shiroe.storage import StateDB
from shiroe.teams import (
    CompiledTeamPlan,
    NoEligibleCapabilityError,
    SelfReviewError,
    compile_team,
    resolve_seat,
    score_capability,
)
from shiroe.teams.resolver import CandidateCapability

REPO_ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _seed_workspace(tmp_path: Path) -> None:
    """Copy the real missions/ + policies/ so the compiler can load them."""
    for name in ("missions", "policies"):
        src = REPO_ROOT / name
        dst = tmp_path / name
        shutil.copytree(src, dst)


def _register_capability(tmp_path: Path, *, name: str,
                         provides: list[str],
                         type_: str = "skill") -> str:
    src = tmp_path / "source" / name
    src.mkdir(parents=True, exist_ok=True)
    (src / "SKILL.md").write_text(f"# {name}\n", encoding="utf-8")
    d = DiscoveredCapability(
        adapter="generic", root="<home>/skills", path=src, kind=type_,
    )
    trust = inspect_source(src)
    cid = register_discovery(tmp_path, d, trust=trust)

    # Manually set the manifest.provides list — inference doesn't
    # discover semantic hints; PR 7 downstream just needs the value.
    store = CapabilityStore(tmp_path)
    try:
        row = store.conn.execute(
            "SELECT id, manifest FROM capability_versions "
            "WHERE capability_id=? ORDER BY created_at DESC LIMIT 1",
            (cid,),
        ).fetchone()
        version_id, raw = row
        manifest = json.loads(raw)
        manifest["provides"] = list(provides)
        store.conn.execute(
            "UPDATE capability_versions SET manifest=? WHERE id=?",
            (json.dumps(manifest, sort_keys=True), version_id),
        )
        store.conn.commit()
    finally:
        store.close()
    approve(tmp_path, cid)
    return cid


# ---------------------------------------------------------------------------
# score_capability
# ---------------------------------------------------------------------------

def _cand(cid: str, provides: list[str], lifecycle: str = "approved") -> CandidateCapability:
    return CandidateCapability(
        id=cid, name=cid, type="skill", lifecycle=lifecycle,
        version_id=f"cv_{cid}", provides=provides, compatibility={},
        manifest={"provides": provides},
    )


def test_score_prefers_seat_provides_match() -> None:
    seat = {"id": "planner", "provides": ["architecture-planning"]}
    match, r_match = score_capability(
        _cand("A", ["architecture-planning", "extras"]), seat,
        active_harness="claude-code",
    )
    no_match, r_no = score_capability(
        _cand("B", ["unrelated"]), seat, active_harness="claude-code",
    )
    assert match > no_match
    assert r_match["provides_overlap"] == ["architecture-planning"]
    assert r_no["provides_overlap"] == []


def test_score_rewards_active_lifecycle() -> None:
    seat = {"id": "s", "provides": ["x"]}
    active, _ = score_capability(
        _cand("A", ["x"], lifecycle="active"), seat,
        active_harness="claude-code",
    )
    approved, _ = score_capability(
        _cand("B", ["x"], lifecycle="approved"), seat,
        active_harness="claude-code",
    )
    assert active > approved


# ---------------------------------------------------------------------------
# resolve_seat — gold assignment (PR 7 acceptance gate #1)
# ---------------------------------------------------------------------------

def test_resolver_picks_highest_scored_candidate(tmp_path: Path) -> None:
    _register_capability(tmp_path, name="architect",
                         provides=["architecture-planning", "dependency-analysis"])
    _register_capability(tmp_path, name="coder",
                         provides=["code-editing", "test-execution"])
    _register_capability(tmp_path, name="dilettante",
                         provides=["nothing-in-particular"])

    store = CapabilityStore(tmp_path)
    try:
        seat = {"id": "planner",
                "provides": ["architecture-planning", "dependency-analysis"]}
        cap, score, rationale = resolve_seat(
            store.conn, seat, active_harness="claude-code",
        )
    finally:
        store.close()
    assert cap.name == "architect"
    assert rationale["provides_score"] == 1.0
    assert rationale["total_score"] > 0


def test_resolver_raises_when_no_eligible(tmp_path: Path) -> None:
    # Register a capability but don't approve it → still quarantined.
    src = tmp_path / "source" / "quarantined-skill"
    src.mkdir(parents=True)
    (src / "SKILL.md").write_text("# x\n", encoding="utf-8")
    d = DiscoveredCapability(
        adapter="generic", root="<home>/skills", path=src, kind="skill",
    )
    register_discovery(tmp_path, d, trust=inspect_source(src))

    store = CapabilityStore(tmp_path)
    try:
        with pytest.raises(NoEligibleCapabilityError):
            resolve_seat(
                store.conn,
                {"id": "planner", "provides": ["architecture-planning"]},
                active_harness="claude-code",
            )
    finally:
        store.close()


# ---------------------------------------------------------------------------
# Independence — PR 7 acceptance gate #2
# ---------------------------------------------------------------------------

def test_resolver_refuses_self_review(tmp_path: Path) -> None:
    """When there's exactly one capability able to fill both implementer
    and verifier seats, the verifier — which is `independent_from:
    [implementer]` — must refuse the same capability rather than silently
    accept a self-review."""
    only_cap = _register_capability(
        tmp_path, name="jack",
        provides=["code-editing", "code-review", "verification"],
    )

    store = CapabilityStore(tmp_path)
    try:
        implementer_seat = {"id": "implementer", "provides": ["code-editing"]}
        cap, _, _ = resolve_seat(
            store.conn, implementer_seat, active_harness="claude-code",
        )
        assert cap.id == only_cap

        verifier_seat = {
            "id": "verifier", "provides": ["code-review", "verification"],
            "constraints": {"independent_from": ["implementer"]},
        }
        with pytest.raises(SelfReviewError):
            resolve_seat(
                store.conn, verifier_seat,
                active_harness="claude-code",
                already_assigned={"implementer": only_cap},
            )
    finally:
        store.close()


# ---------------------------------------------------------------------------
# compile_team — end-to-end
# ---------------------------------------------------------------------------

def test_compile_team_build_mission_persists_plan(tmp_path: Path) -> None:
    _seed_workspace(tmp_path)
    _register_capability(tmp_path, name="architect",
                         provides=["architecture-planning", "dependency-analysis"])
    _register_capability(tmp_path, name="coder",
                         provides=["code-editing", "test-execution"])
    _register_capability(tmp_path, name="reviewer",
                         provides=["code-review", "verification"])

    plan = compile_team(
        tmp_path, task_id="task_demo", mission_id="build",
        policy_id="balanced", active_harness="claude-code",
    )
    assert isinstance(plan, CompiledTeamPlan)
    assert plan.mission_id == "build"
    assert plan.policy_id == "balanced"
    assert [a.seat_id for a in plan.assignments] == \
           ["planner", "implementer", "verifier"]
    seat_to_name = {a.seat_id: a.capability_id.split(":", 1)[1] for a in plan.assignments}
    assert seat_to_name["planner"] == "architect"
    assert seat_to_name["implementer"] == "coder"
    assert seat_to_name["verifier"] == "reviewer"

    # SQLite side: rows persisted
    conn = sqlite3.connect(tmp_path / "memory" / "state" / "zeref2.sqlite")
    try:
        (state,) = conn.execute(
            "SELECT state FROM team_runs WHERE id=?", (plan.run_id,),
        ).fetchone()
        assert state == "COMPILED"
        (n_assignments,) = conn.execute(
            "SELECT COUNT(*) FROM team_assignments WHERE run_id=?",
            (plan.run_id,),
        ).fetchone()
        assert n_assignments == 3
        (n_steps,) = conn.execute(
            "SELECT COUNT(*) FROM execution_steps WHERE run_id=?",
            (plan.run_id,),
        ).fetchone()
        assert n_steps == 3
    finally:
        conn.close()


def test_compiled_plan_stores_rationale(tmp_path: Path) -> None:
    _seed_workspace(tmp_path)
    _register_capability(tmp_path, name="architect",
                         provides=["architecture-planning"])
    _register_capability(tmp_path, name="coder",
                         provides=["code-editing"])
    _register_capability(tmp_path, name="reviewer",
                         provides=["code-review"])

    plan = compile_team(
        tmp_path, task_id="task_r", mission_id="build",
    )
    conn = sqlite3.connect(tmp_path / "memory" / "state" / "zeref2.sqlite")
    try:
        rows = conn.execute(
            "SELECT seat_id, rationale FROM team_assignments WHERE run_id=?",
            (plan.run_id,),
        ).fetchall()
    finally:
        conn.close()
    for _, raw in rows:
        rationale = json.loads(raw)
        assert "provides_overlap" in rationale
        assert "total_score" in rationale


def test_compile_refuses_when_no_capability_fits_seat(tmp_path: Path) -> None:
    _seed_workspace(tmp_path)
    # Only a capability that fits *nothing* the mission needs: the resolver
    # scores it against the seat and still picks it (the highest of zero
    # good options) for planner and implementer, then rejects the verifier
    # seat because the only remaining candidate violates independence.
    # Either failure mode is acceptable — both mean "cannot compile".
    _register_capability(tmp_path, name="wanderer",
                         provides=["irrelevant"])
    with pytest.raises((NoEligibleCapabilityError, SelfReviewError)):
        compile_team(tmp_path, task_id="task_x", mission_id="build")


def test_compile_plan_contains_no_provider_model_ids(tmp_path: Path) -> None:
    _seed_workspace(tmp_path)
    _register_capability(tmp_path, name="architect", provides=["architecture-planning"])
    _register_capability(tmp_path, name="coder", provides=["code-editing"])
    _register_capability(tmp_path, name="reviewer", provides=["code-review"])
    plan = compile_team(tmp_path, task_id="task_np", mission_id="build")
    dumped = json.dumps(plan.to_dict())
    for banned in ("claude-opus", "claude-sonnet", "claude-haiku", "claude-fable",
                   "gpt-4", "gpt-5", "gemini-1", "gemini-2"):
        assert banned not in dumped
