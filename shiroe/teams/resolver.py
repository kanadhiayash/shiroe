"""Resolver — score executable capabilities against a mission seat.

Master plan §8.7 lists 13 factors; every non-observable factor defaults
to a neutral value (0.5) so the resolver stays deterministic even when
recent-success / benchmark rows haven't been populated. Ties broken by
capability_id ascending.

Seat + capability metadata:
- seat.provides[]        — list of capability domains the seat expects
- seat.reasoning_class   — one of fast / balanced / deep / frontier
- capability.provides[]  — from the manifest
- capability.type        — skill / agent / cli / mcp_server / ...
- capability_versions.compatibility — harness compat JSON

Scores are in [0, 1]. A capability that fails a hard filter (lifecycle
not executable, seat requires an independent slot already used, harness
incompatible) is excluded — never silently downweighted.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from shiroe.capabilities.lifecycle import EXECUTABLE_STATES
from shiroe.capabilities.store import CapabilityStore


class NoEligibleCapabilityError(RuntimeError):
    """No approved capability satisfies the seat requirements."""


class SelfReviewError(RuntimeError):
    """Independence constraint violated (e.g. verifier == implementer)."""


@dataclass
class CandidateCapability:
    id: str
    name: str
    type: str
    lifecycle: str
    version_id: str
    provides: list[str]
    compatibility: dict
    manifest: dict


def _load_candidates(conn: sqlite3.Connection) -> list[CandidateCapability]:
    rows = conn.execute(
        """
        SELECT c.id, c.name, c.type, c.lifecycle, cv.id, cv.manifest,
               cv.compatibility
        FROM capabilities c
        JOIN (
            SELECT capability_id, MAX(created_at) AS latest
            FROM capability_versions
            GROUP BY capability_id
        ) latest_cv
          ON latest_cv.capability_id = c.id
        JOIN capability_versions cv
          ON cv.capability_id = c.id
         AND cv.created_at = latest_cv.latest
        WHERE c.lifecycle IN ('approved', 'benchmarked', 'active')
        """
    ).fetchall()
    out: list[CandidateCapability] = []
    for cid, name, ctype, lifecycle, version_id, manifest_json, compat_json in rows:
        manifest = json.loads(manifest_json) if manifest_json else {}
        compat = json.loads(compat_json) if compat_json else {}
        out.append(CandidateCapability(
            id=cid, name=name, type=ctype, lifecycle=lifecycle,
            version_id=version_id,
            provides=list(manifest.get("provides") or []),
            compatibility=compat,
            manifest=manifest,
        ))
    return out


def score_capability(cap: CandidateCapability, seat: dict,
                     *, active_harness: str) -> tuple[float, dict]:
    rationale: dict = {}
    score = 0.0

    # 1. seat.provides match — dominant signal
    seat_provides = set(seat.get("provides") or [])
    overlap = seat_provides & set(cap.provides)
    provides_score = (len(overlap) / max(1, len(seat_provides))) if seat_provides else 0.5
    score += 0.45 * provides_score
    rationale["provides_overlap"] = sorted(overlap)
    rationale["provides_score"] = round(provides_score, 3)

    # 2. lifecycle preference (active > benchmarked > approved)
    lc_weight = {"active": 1.0, "benchmarked": 0.85, "approved": 0.7}
    lc_score = lc_weight.get(cap.lifecycle, 0.5)
    score += 0.15 * lc_score
    rationale["lifecycle_score"] = lc_score

    # 3. harness compatibility
    harnesses = list((cap.compatibility or {}).get("harnesses") or [])
    if not harnesses or active_harness in harnesses:
        harness_score = 1.0
    else:
        harness_score = 0.3
    score += 0.15 * harness_score
    rationale["harness_score"] = harness_score

    # 4. type affinity to seat.reasoning_class — cheap heuristic
    type_score = 0.5
    rationale["type_score"] = type_score
    score += 0.05 * type_score

    # 5. neutral defaults for the remaining §8.7 factors until PR 8/10
    #    (benchmark score, recent success, freshness, output-schema
    #    compat, permission risk, cost, latency, provider diversity)
    score += 0.20 * 0.5
    rationale["defaults_score"] = 0.5

    return score, rationale


def _harness_compatible(cap: CandidateCapability, active_harness: str) -> bool:
    harnesses = list((cap.compatibility or {}).get("harnesses") or [])
    if not harnesses:
        return True  # unrestricted
    return active_harness in harnesses


def resolve_seat(
    conn: sqlite3.Connection,
    seat: dict,
    *,
    active_harness: str,
    already_assigned: dict[str, str] | None = None,
) -> tuple[CandidateCapability, float, dict]:
    """Return (capability, score, rationale) for the best fit.

    ``already_assigned`` maps seat_id → capability_id so independence
    constraints can be enforced. Raises ``SelfReviewError`` if this
    seat's ``independent_from`` list would be violated by every remaining
    candidate.
    """
    already_assigned = already_assigned or {}
    forbidden_ids: set[str] = set()
    for other_seat_id in (seat.get("constraints") or {}).get("independent_from") or []:
        cap_id = already_assigned.get(other_seat_id)
        if cap_id:
            forbidden_ids.add(cap_id)

    candidates = _load_candidates(conn)
    if not candidates:
        raise NoEligibleCapabilityError(
            f"seat {seat['id']!r}: no approved capabilities in the registry"
        )

    scored: list[tuple[float, str, CandidateCapability, dict]] = []
    filtered_out: list[str] = []
    for cap in candidates:
        if cap.lifecycle not in EXECUTABLE_STATES:
            filtered_out.append(f"{cap.id}: lifecycle {cap.lifecycle}")
            continue
        if not _harness_compatible(cap, active_harness):
            filtered_out.append(f"{cap.id}: harness incompatible")
            continue
        if cap.id in forbidden_ids:
            filtered_out.append(
                f"{cap.id}: independence constraint (already in "
                f"{[s for s, c in already_assigned.items() if c == cap.id]})"
            )
            continue
        score, rationale = score_capability(cap, seat, active_harness=active_harness)
        scored.append((score, cap.id, cap, rationale))

    if not scored:
        if forbidden_ids and any(
            c.id in forbidden_ids for c in candidates
            if c.lifecycle in EXECUTABLE_STATES
        ):
            raise SelfReviewError(
                f"seat {seat['id']!r}: only remaining capabilities violate "
                f"independence constraint {list(forbidden_ids)}"
            )
        raise NoEligibleCapabilityError(
            f"seat {seat['id']!r}: no eligible capability. "
            f"Filtered: {filtered_out}"
        )

    # Highest score wins; ties broken by capability id ascending (deterministic).
    scored.sort(key=lambda t: (-t[0], t[1]))
    winner_score, _, winner_cap, winner_rationale = scored[0]
    winner_rationale["total_score"] = round(winner_score, 4)
    winner_rationale["candidates_considered"] = len(scored)
    winner_rationale["forbidden_by_independence"] = sorted(forbidden_ids)
    return winner_cap, winner_score, winner_rationale
