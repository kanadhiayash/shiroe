"""Bi-temporal fact versioning over the atom store.

Two independent time axes, never collapsed into one:

- **Valid time** (``valid_from`` / ``valid_until``) — when the fact was true
  IN THE WORLD. Half-open interval: valid from (inclusive) until (exclusive).
  A null bound means "unknown/open on that side" — never fabricate one.
- **Transaction time** (``recorded_at`` / ``superseded_at``) — when Zeref
  LEARNED (and, if applicable, un-learned) the fact. A null ``superseded_at``
  means the row is still the current belief.

"The launch date was always Sept 1, but we only found out Tuesday" has an
early ``valid_from`` and a late ``recorded_at`` — the two axes answer
different questions and must be queryable independently:
``as_of_valid(date)`` = what was true on that date; ``as_of_recorded(date)``
= what Zeref believed as of that date.

Supersession never destructively updates a row: the prior atom's
``superseded_at`` is closed via :func:`zeref.memory.atom_store.AtomStore.patch`
(which rewrites the row, it does not delete it) and the replacement is a new
appended atom. Full history stays queryable via ``as_of_recorded``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from zeref.memory.atom_store import AtomStore
from zeref.memory.schemas import utc_now_iso


def _parse(value: str | None) -> datetime | None:
    """Parse an ISO-8601 timestamp/date to an aware datetime, or None."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _ref(ref: str | None) -> datetime:
    return _parse(ref) or datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Valid-time axis
# ---------------------------------------------------------------------------

def is_valid_at(atom: dict[str, Any], ref: str | None = None) -> bool:
    """True when ``atom`` is valid-in-the-world at ``ref`` (default: now).

    Half-open interval [valid_from, valid_until). A null valid_from means
    "valid since before we have a bound"; a null valid_until means "still
    valid, no end known".
    """
    at = _ref(ref)
    start = _parse(atom.get("valid_from"))
    end = _parse(atom.get("valid_until"))
    if start is not None and at < start:
        return False
    if end is not None and at >= end:
        return False
    return True


def as_of_valid(atoms: list[dict[str, Any]], ref: str | None = None) -> list[dict[str, Any]]:
    """Atoms that were true in the world at ``ref`` — the valid-time axis.

    Pure in-memory filter (no I/O): callers loop-calling this should load
    ``atoms`` once via ``AtomStore.load()`` and reuse the list.
    """
    return [atom for atom in atoms if is_valid_at(atom, ref)]


# ---------------------------------------------------------------------------
# Transaction-time axis
# ---------------------------------------------------------------------------

def is_recorded_at(atom: dict[str, Any], ref: str | None = None) -> bool:
    """True when Zeref's belief-set included ``atom`` as of ``ref``.

    Half-open interval [recorded_at, superseded_at). A null superseded_at
    means the atom was never superseded (still current knowledge).
    """
    at = _ref(ref)
    recorded = _parse(atom.get("recorded_at")) or _parse(atom.get("created_at"))
    superseded = _parse(atom.get("superseded_at"))
    if recorded is not None and at < recorded:
        return False
    if superseded is not None and at >= superseded:
        return False
    return True


def as_of_recorded(atoms: list[dict[str, Any]], ref: str | None = None) -> list[dict[str, Any]]:
    """Atoms Zeref believed as of ``ref`` — the transaction-time axis.

    Answers "what did we believe on date X", independent of whether that
    belief was ever, later, true in the world.
    """
    return [atom for atom in atoms if is_recorded_at(atom, ref)]


# ---------------------------------------------------------------------------
# Combined view
# ---------------------------------------------------------------------------

def is_current(atom: dict[str, Any], ref: str | None = None) -> bool:
    """True when ``atom`` is valid now (at ``ref``) AND not superseded."""
    return atom.get("superseded_at") is None and is_valid_at(atom, ref)


def current(atoms: list[dict[str, Any]], ref: str | None = None) -> list[dict[str, Any]]:
    """Atoms valid at ``ref`` (default: now) and not superseded."""
    return [atom for atom in atoms if is_current(atom, ref)]


# ---------------------------------------------------------------------------
# Supersession
# ---------------------------------------------------------------------------

def supersede_fact(
    store: AtomStore,
    old_id: str,
    new_atom: dict[str, Any],
    *,
    at: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Close ``old_id``'s transaction-time interval and append its replacement.

    Never destructive: the prior row is rewritten in place with
    ``superseded_at`` set (status becomes ``superseded``); its claim, evidence,
    and full history stay queryable via ``as_of_recorded``. The new atom is a
    normal append and should already carry its own ``valid_from``/``valid_until``.
    """
    now = at or utc_now_iso()
    if new_atom.get("recorded_at") is None:
        new_atom = {**new_atom, "recorded_at": now}
    old = store.patch(old_id, {"status": "superseded", "superseded_at": now})
    new = store.append(new_atom)
    return old, new


# ---------------------------------------------------------------------------
# Contradiction integration
# ---------------------------------------------------------------------------

def valid_intervals_overlap(left: dict[str, Any], right: dict[str, Any]) -> bool:
    """True when two atoms' valid-time intervals overlap.

    Two facts about the same subject+attribute with NON-overlapping valid
    intervals are a legitimate update over time (e.g. a price that changed),
    not a contradiction — even though their claim values disagree. Only
    overlapping intervals with disagreeing values are a real conflict.

    Intervals are half-open [valid_from, valid_until); a null bound is open
    on that side. When neither atom has ANY valid-time bound, both intervals
    are fully open and trivially overlap — this preserves today's behavior
    (flag as a contradiction) for atoms with no temporal information, rather
    than silently waving through an unprovable "update".
    """
    left_start = _parse(left.get("valid_from"))
    left_end = _parse(left.get("valid_until"))
    right_start = _parse(right.get("valid_from"))
    right_end = _parse(right.get("valid_until"))
    if left_end is not None and right_start is not None and left_end <= right_start:
        return False
    if right_end is not None and left_start is not None and right_end <= left_start:
        return False
    return True


# ---------------------------------------------------------------------------
# Ranking
# ---------------------------------------------------------------------------

def rank_key(atom: dict[str, Any], ref: str | None = None) -> tuple[int, int]:
    """Dominance sort key (ascending = better) for bi-temporal ranking.

    Prefers atoms valid at ``ref`` over not-valid-at-ref, and current (not
    superseded) over superseded. A superseded fact never outranks a current
    one, however well it matches the query.

    Deliberately excludes recency. Both components here are small integers, so
    they tie often and let the caller's relevance term decide. ``recorded_at``
    is a continuous value that almost never ties, so folding it in here would
    silently decide every comparison before relevance was ever consulted — see
    :func:`recency_key`, which callers must apply *after* their score term.
    """
    not_valid = 0 if is_valid_at(atom, ref) else 1
    superseded = 1 if atom.get("superseded_at") is not None else 0
    return (not_valid, superseded)


def recency_key(atom: dict[str, Any]) -> float:
    """Tie-breaker (ascending = better): more recently recorded wins.

    Only meaningful *after* a relevance term. Sorting by this before score
    makes recency outrank relevance, which is not the ranking contract.
    """
    recorded = _parse(atom.get("recorded_at")) or _parse(atom.get("created_at"))
    return -recorded.timestamp() if recorded is not None else 0.0
