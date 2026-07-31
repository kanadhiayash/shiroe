"""Bi-temporal fact versioning: two independent time axes, supersession,
contradiction/update discrimination, migration, and ranking.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from shiroe.memory.atom_store import AtomStore
from shiroe.memory.bitemporal import (
    as_of_recorded,
    as_of_valid,
    current,
    is_current,
    rank_key,
    supersede_fact,
    valid_intervals_overlap,
)
from shiroe.memory.contradictions import detect_conflict
from shiroe.memory.schemas import create_atom
from shiroe.memory.search import search_atoms

REPO_ROOT = Path(__file__).resolve().parent.parent
MIGRATION_SCRIPT = REPO_ROOT / "scripts" / "migrate-bitemporal-facts.py"


def _fact(claim: str, **overrides) -> dict:
    defaults = dict(
        atom_type="fact",
        claim=claim,
        summary=claim,
        source="manual:bitemporal-test",
        provenance=claim,
    )
    defaults.update(overrides)
    return create_atom(**defaults)


# ---------------------------------------------------------------------------
# 1. Two independent axes — as_of_valid vs as_of_recorded must diverge
# ---------------------------------------------------------------------------

def test_valid_time_and_transaction_time_are_independent_axes() -> None:
    # "The launch date was always Sept 1, but we only found out Tuesday":
    # true in the world since June 1; Zeref only learned it on July 22.
    atom = _fact(
        "Launch date is 2026-09-01",
        valid_from="2026-06-01T00:00:00Z",
        valid_until=None,
        recorded_at="2026-07-22T00:00:00Z",
        created_at="2026-07-22T00:00:00Z",
    )

    between = "2026-07-01T00:00:00Z"  # after valid_from, before recorded_at
    assert as_of_valid([atom], between) == [atom]
    assert as_of_recorded([atom], between) == []  # THE divergence: different answers

    after_both = "2026-08-01T00:00:00Z"
    assert as_of_valid([atom], after_both) == [atom]
    assert as_of_recorded([atom], after_both) == [atom]

    before_both = "2026-05-01T00:00:00Z"
    assert as_of_valid([atom], before_both) == []
    assert as_of_recorded([atom], before_both) == []


def test_as_of_recorded_survives_supersession_as_of_recorded_still_sees_old_belief() -> None:
    # What Zeref believed on date X should still include a fact that was
    # later superseded, as long as X is before the supersession.
    atom = _fact(
        "Rate limit is 100 rps",
        recorded_at="2026-01-01T00:00:00Z",
        superseded_at="2026-06-01T00:00:00Z",
        status="superseded",
    )
    assert as_of_recorded([atom], "2026-03-01T00:00:00Z") == [atom]
    assert as_of_recorded([atom], "2026-07-01T00:00:00Z") == []


# ---------------------------------------------------------------------------
# 2. Supersession preserves history; never destructive
# ---------------------------------------------------------------------------

def test_supersede_fact_closes_prior_row_and_keeps_it_queryable(fake_repo: Path) -> None:
    store = AtomStore(fake_repo)
    old = store.append(_fact("Price is $10", recorded_at="2026-01-01T00:00:00Z"))
    new_candidate = _fact(
        "Price is $12",
        valid_from="2026-06-01T00:00:00Z",
        recorded_at="2026-06-01T00:00:00Z",
    )

    old_after, new_atom = supersede_fact(store, old["id"], new_candidate, at="2026-06-01T00:00:00Z")

    assert old_after["status"] == "superseded"
    assert old_after["superseded_at"] == "2026-06-01T00:00:00Z"
    assert old_after["claim"] == "Price is $10"  # content never overwritten

    # Old row is still on disk and retrievable by id — history preserved.
    reloaded_old = store.get(old["id"])
    assert reloaded_old is not None
    assert reloaded_old["claim"] == "Price is $10"
    assert reloaded_old["status"] == "superseded"

    # Both rows queryable; only the new one is "active".
    all_facts = {atom["id"] for atom in store.load(atom_type="fact")}
    assert {old["id"], new_atom["id"]} <= all_facts
    active = store.load(atom_type="fact", status="active")
    assert [atom["id"] for atom in active] == [new_atom["id"]]


# ---------------------------------------------------------------------------
# 3. Update vs contradiction — both directions
# ---------------------------------------------------------------------------

def test_nonoverlapping_valid_intervals_is_update_not_contradiction() -> None:
    old_price = _fact(
        "Price is $10",
        valid_from="2026-01-01T00:00:00Z",
        valid_until="2026-06-01T00:00:00Z",
    )
    new_price = _fact(
        "Price is $12",
        valid_from="2026-06-01T00:00:00Z",
        valid_until=None,
    )
    assert valid_intervals_overlap(old_price, new_price) is False
    assert detect_conflict(old_price, new_price) is None
    assert detect_conflict(new_price, old_price) is None  # order-independent


def test_overlapping_valid_intervals_with_incompatible_values_is_contradiction() -> None:
    claim_a = _fact(
        "Price is $10",
        valid_from="2026-01-01T00:00:00Z",
        valid_until="2026-12-01T00:00:00Z",
    )
    claim_b = _fact(
        "Price is $12",
        valid_from="2026-03-01T00:00:00Z",
        valid_until="2026-09-01T00:00:00Z",
    )
    assert valid_intervals_overlap(claim_a, claim_b) is True
    conflict = detect_conflict(claim_a, claim_b)
    assert conflict is not None
    assert detect_conflict(claim_b, claim_a) is not None  # order-independent


def test_no_temporal_data_still_flags_as_contradiction() -> None:
    # Legacy/backfilled atoms with no valid-time bounds at all: both
    # intervals are fully open and trivially overlap. This preserves
    # today's behavior instead of silently waving through an unprovable
    # "update" — see test_ws3_memory_coherence.py's two-launch-dates case.
    left = _fact("Launch date is 2026-09-01")
    right = _fact("Launch date is 2026-10-15")
    assert valid_intervals_overlap(left, right) is True
    assert detect_conflict(left, right) is not None


# ---------------------------------------------------------------------------
# 4. Migration: idempotent, never loses or fabricates data
# ---------------------------------------------------------------------------

def _run_migration(atom_dir: Path, *, apply: bool) -> subprocess.CompletedProcess:
    args = [sys.executable, str(MIGRATION_SCRIPT), "--atom-dir", str(atom_dir)]
    if apply:
        args.append("--apply")
    return subprocess.run(args, capture_output=True, text=True)


def test_migration_backfills_recorded_at_and_is_idempotent(tmp_path: Path) -> None:
    atom_dir = tmp_path / "l1_atoms"
    atom_dir.mkdir()
    legacy_atom = {
        "id": "fact_legacy0001",
        "type": "fact",
        "claim": "Legacy fact with no bitemporal fields",
        "summary": "Legacy fact with no bitemporal fields",
        "source": "manual:legacy",
        "source_type": "manual",
        "evidence": "unverified",
        "confidence": "unknown",
        "status": "active",
        "created_at": "2025-01-01T00:00:00Z",
        "observed_at": None,
        "last_confirmed_at": None,
        "valid_from": None,
        "valid_until": None,
        "entities": [],
        "tags": [],
        "links": [],
        "privacy": "unknown",
        "provenance": "",
        # recorded_at / superseded_at deliberately absent (pre-migration shape)
    }
    facts_path = atom_dir / "facts.jsonl"
    facts_path.write_text(json.dumps(legacy_atom) + "\n", encoding="utf-8")

    dry = _run_migration(atom_dir, apply=False)
    assert dry.returncode == 0, dry.stderr
    # Dry-run never writes.
    unchanged = json.loads(facts_path.read_text(encoding="utf-8").splitlines()[0])
    assert "recorded_at" not in unchanged

    applied = _run_migration(atom_dir, apply=True)
    assert applied.returncode == 0, applied.stderr
    migrated = json.loads(facts_path.read_text(encoding="utf-8").splitlines()[0])
    assert migrated["recorded_at"] == "2025-01-01T00:00:00Z"  # backfilled from created_at
    assert migrated["superseded_at"] is None  # never fabricated
    assert migrated["valid_from"] is None  # never fabricated
    assert migrated["claim"] == "Legacy fact with no bitemporal fields"  # nothing lost

    # Idempotent: re-running --apply on already-migrated data changes nothing.
    before = facts_path.read_text(encoding="utf-8")
    second_apply = _run_migration(atom_dir, apply=True)
    assert second_apply.returncode == 0, second_apply.stderr
    after = facts_path.read_text(encoding="utf-8")
    assert before == after

    # And the migrated row now satisfies the current atom schema.
    from shiroe.memory.schemas import validate_atom
    validate_atom(migrated)


def test_migration_handles_missing_atom_dir_gracefully(tmp_path: Path) -> None:
    result = _run_migration(tmp_path / "does-not-exist", apply=False)
    assert result.returncode == 0
    assert "nothing to migrate" in result.stdout


# ---------------------------------------------------------------------------
# 5. Ranking: valid-at-reference-time and current beat superseded
# ---------------------------------------------------------------------------

def test_rank_key_prefers_valid_and_current_over_superseded() -> None:
    ref = "2026-07-01T00:00:00Z"
    current_valid = _fact(
        "Rate limit is 100 rps",
        valid_from="2026-01-01T00:00:00Z",
        recorded_at="2026-01-01T00:00:00Z",
    )
    superseded = _fact(
        "Rate limit is 50 rps",
        valid_from="2025-01-01T00:00:00Z",
        recorded_at="2025-01-01T00:00:00Z",
        superseded_at="2026-01-01T00:00:00Z",
        status="superseded",
    )
    not_yet_valid = _fact(
        "Rate limit is 200 rps",
        valid_from="2026-12-01T00:00:00Z",
        recorded_at="2026-06-01T00:00:00Z",
    )

    assert is_current(current_valid, ref) is True
    assert is_current(superseded, ref) is False
    assert is_current(not_yet_valid, ref) is False  # not valid yet, though not superseded
    assert current([current_valid, superseded, not_yet_valid], ref) == [current_valid]

    ranked = sorted(
        [superseded, not_yet_valid, current_valid],
        key=lambda atom: rank_key(atom, ref),
    )
    assert ranked[0] is current_valid  # superseded and not-yet-valid never outrank it


def test_search_ranking_never_lets_superseded_outrank_current(fake_repo: Path) -> None:
    store = AtomStore(fake_repo)
    old = store.append(
        _fact(
            "Zeref rate limit is 100 rps",
            recorded_at="2026-01-01T00:00:00Z",
            superseded_at="2026-06-01T00:00:00Z",
            status="superseded",
            created_at="2026-01-01T00:00:00Z",
        )
    )
    new = store.append(
        _fact(
            "Zeref rate limit is 100 rps",
            recorded_at="2026-06-01T00:00:00Z",
            created_at="2026-06-01T00:00:00Z",
            provenance="Zeref rate limit is 100 rps v2",
        )
    )
    assert old["id"] != new["id"]

    result = search_atoms(fake_repo, "rate limit", atom_type="fact", status=None)
    ids_in_order = [m["atom"]["id"] for m in result["matches"]]
    assert ids_in_order[0] == new["id"]
    assert ids_in_order.index(new["id"]) < ids_in_order.index(old["id"])


def test_recency_breaks_ties_but_never_overrides_relevance(fake_repo: Path) -> None:
    """Two atoms, both valid and both current, so rank_key's dominance
    components tie. Ordering must then fall to text score — a barely-relevant
    atom does not win just for being recorded later. `recorded_at` is a
    tie-breaker among equally-scored matches, not a term that outranks score.
    """
    store = AtomStore(fake_repo)
    relevant = store.append(
        _fact(
            "launch code colour is vermilion, the launch code vermilion",
            recorded_at="2026-01-01T00:00:00Z",
            created_at="2026-01-01T00:00:00Z",
        )
    )
    recent_but_weak = store.append(
        _fact(
            "gardening notes about tulips, taken near the launch",
            recorded_at="2026-06-01T00:00:00Z",
            created_at="2026-06-01T00:00:00Z",
        )
    )
    assert relevant["id"] != recent_but_weak["id"]

    result = search_atoms(fake_repo, "launch code vermilion", atom_type="fact", status=None)
    ids_in_order = [m["atom"]["id"] for m in result["matches"]]
    # Both match ("launch"), so both are present and the comparison is real.
    assert set(ids_in_order) == {relevant["id"], recent_but_weak["id"]}
    assert ids_in_order[0] == relevant["id"]


def test_recency_still_breaks_ties_between_equally_scored_atoms(fake_repo: Path) -> None:
    """The other half of the contract: when score genuinely ties, the more
    recently recorded atom wins. Guards against 'fixing' the rule above by
    dropping recency from the sort altogether.
    """
    store = AtomStore(fake_repo)
    older = store.append(
        _fact(
            "deploy window is Tuesday",
            recorded_at="2026-01-01T00:00:00Z",
            created_at="2026-01-01T00:00:00Z",
        )
    )
    newer = store.append(
        _fact(
            "deploy window is Tuesday",
            recorded_at="2026-06-01T00:00:00Z",
            created_at="2026-06-01T00:00:00Z",
            provenance="deploy window is Tuesday v2",
        )
    )
    assert older["id"] != newer["id"]

    result = search_atoms(fake_repo, "deploy window", atom_type="fact", status=None)
    ids_in_order = [m["atom"]["id"] for m in result["matches"]]
    assert ids_in_order[0] == newer["id"]
