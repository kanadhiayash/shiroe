"""Deterministic lexical subject-predicate-object extraction.

No NER, no model calls -- plain regex over an atom's claim text, against a
fixed, curated predicate vocabulary. This is a precision-first extractor:
a wrong triple silently corrupts every future query that trusts it, so a
claim that doesn't cleanly match one of these shapes yields zero triples.
That is the intended, common outcome (see the precision-floor test in
tests/test_retrieval_ranking.py) -- low recall is an accepted tradeoff,
low precision is not.

Guardrails, in order:
  1. Fixed predicate vocabulary only -- no generic copula ("is"/"are") on
     its own, because on this corpus that pattern's false-positive rate
     (adjectives, negations, descriptions) is too high to trust.
  2. Subject/object must each be a short phrase (<= 6 words), not a pronoun
     ("it", "this", ...), and not a compound ("X and Y").
  3. If the object contains a *second* predicate keyword, the sentence is
     asserting an ambiguous chain of relations ("uses Y which depends on
     Z") -- extract nothing rather than guess which one.
"""

from __future__ import annotations

import re
from typing import Any


# Longest phrase first so "is responsible for" is tried as a whole before
# any shorter alternative could partially consume it.
PREDICATES: tuple[str, ...] = (
    "is responsible for",
    "is owned by",
    "reports to",
    "depends on",
    "belongs to",
    "supersedes",
    "replaces",
    "owns",
    "uses",
    "manages",
)

_PREDICATE_PATTERN = "|".join(re.escape(p) for p in sorted(PREDICATES, key=len, reverse=True))

_TRIPLE_RE = re.compile(
    rf"^(?P<subject>[^,;]+?)\s+(?P<predicate>{_PREDICATE_PATTERN})\s+(?P<object>[^,;.!?]+?)[.!?]?$",
    re.IGNORECASE,
)

_PRONOUNS = {"it", "this", "that", "these", "those", "he", "she", "they", "we", "i", "you"}
_MAX_PHRASE_WORDS = 6

# Fixed, not calibrated against real outcomes -- a deterministic marker that
# "a pattern in PREDICATES matched cleanly," nothing more. Downstream code
# should treat it as a tie-breaker, not a probability.
TRIPLE_CONFIDENCE = 0.8


def _clean_phrase(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().strip(".,;:!?")


def _is_plausible_entity_phrase(phrase: str) -> bool:
    words = phrase.split()
    if not words or len(words) > _MAX_PHRASE_WORDS:
        return False
    if words[0].lower() in _PRONOUNS:
        return False
    if any(word.lower() in {"and", "or"} for word in words):
        return False  # compound subject/object is ambiguous -- skip it
    return True


def extract_triples(atom: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract zero or one (subject, predicate, object) triple from an atom's claim.

    Returns a list (0 or 1 items today) so callers never special-case arity,
    and so a future multi-clause splitter can extend this without changing
    the return contract.
    """
    claim = str(atom.get("claim", "")).strip()
    if not claim:
        return []
    match = _TRIPLE_RE.match(claim)
    if not match:
        return []

    subject = _clean_phrase(match.group("subject"))
    predicate = match.group("predicate").lower()
    obj = _clean_phrase(match.group("object"))

    if not _is_plausible_entity_phrase(subject) or not _is_plausible_entity_phrase(obj):
        return []

    # A second predicate keyword inside the object means the sentence
    # asserts a chain of relations -- ambiguous which one the claim intends.
    if any(re.search(rf"\b{re.escape(p)}\b", obj, re.IGNORECASE) for p in PREDICATES if p != predicate):
        return []

    return [{
        "subject": subject,
        "predicate": predicate,
        "object": obj,
        "source_atom_id": str(atom.get("id", "")),
        "confidence": TRIPLE_CONFIDENCE,
    }]


def query_triples(
    root: Any,
    *,
    subject: str | None = None,
    predicate: str | None = None,
    object: str | None = None,  # noqa: A002 - matches the SPO column name
    limit: int = 20,
    as_of: str | None = None,
) -> dict[str, Any]:
    """Read extracted triples from the SQLite index (memory/indexes/zeref.sqlite).

    Triples are index-only, same as the entities/links tables `indexer.py`
    already builds -- there is no JSONL fallback. Run `zeref memory index`
    (rebuild_index) after adding atoms to populate this table.

    Ranked bi-temporally the same way search_atoms() is (see
    zeref.memory.bitemporal.rank_key): a triple from a superseded or
    not-currently-valid atom never outranks one from a current atom. The
    triples table itself has no supersession awareness -- it's keyed only on
    source_atom_id -- so each candidate is joined back to its source atom's
    raw_json to read recorded_at/superseded_at/valid_from/valid_until.
    """
    import json
    import sqlite3
    from pathlib import Path

    from zeref.memory.bitemporal import rank_key
    from zeref.memory.indexer import INDEX_PATH

    db_path = Path(root) / INDEX_PATH
    if not db_path.exists():
        return {"index_available": False, "matches": []}

    filters = []
    params: list[str] = []
    if subject:
        filters.append("triples.subject LIKE ?")
        params.append(f"%{subject}%")
    if predicate:
        filters.append("triples.predicate = ?")
        params.append(predicate)
    if object:
        filters.append("triples.object LIKE ?")
        params.append(f"%{object}%")
    where = " WHERE " + " AND ".join(filters) if filters else ""

    conn = sqlite3.connect(db_path)
    try:
        conn.execute("SELECT 1 FROM triples LIMIT 1")
    except sqlite3.OperationalError:
        conn.close()
        return {"index_available": False, "matches": []}
    try:
        # ponytail: over-fetch a bounded window (not the whole table) so the
        # bitemporal re-rank below has candidates beyond `limit` to work
        # with -- same tradeoff as search.py's _fts_query. Ceiling: a
        # superseded triple ranked beyond the window is still invisible to
        # the re-rank; raise the multiplier if that proves visible in
        # practice.
        rows = conn.execute(
            f"""
            SELECT triples.subject, triples.predicate, triples.object,
                   triples.source_atom_id, triples.confidence, atoms.raw_json
            FROM triples
            JOIN atoms ON atoms.id = triples.source_atom_id
            {where}
            ORDER BY triples.confidence DESC, triples.subject, triples.predicate, triples.object
            LIMIT ?
            """,
            [*params, min(limit * 4, 200)],
        ).fetchall()
    finally:
        conn.close()

    candidates = []
    for position, row in enumerate(rows):
        atom = json.loads(row[5])
        candidates.append({
            "match": {
                "subject": row[0],
                "predicate": row[1],
                "object": row[2],
                "source_atom_id": row[3],
                "confidence": row[4],
            },
            "atom": atom,
            "position": position,
        })
    candidates.sort(key=lambda item: (*rank_key(item["atom"], as_of), item["position"]))

    return {
        "index_available": True,
        "matches": [item["match"] for item in candidates[:limit]],
    }
