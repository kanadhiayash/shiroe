"""Deterministic atom search with SQLite FTS and JSONL fallback."""

from __future__ import annotations

import json
import math
import re
import sqlite3
import unicodedata
from pathlib import Path
from typing import Any

from shiroe.memory.atom_store import AtomStore
from shiroe.memory.bitemporal import rank_key, recency_key
from shiroe.memory.expand import expand_tokens
from shiroe.memory.indexer import INDEX_PATH


# Scripts without whitespace word boundaries (CJK). Ranges cover the common
# Han ideograph blocks plus Hiragana/Katakana — enough for real-world queries
# without pulling in a segmentation dependency.
_CJK_RANGES = (
    (0x4E00, 0x9FFF),   # CJK Unified Ideographs
    (0x3400, 0x4DBF),   # CJK Extension A
    (0xF900, 0xFAFF),   # CJK Compatibility Ideographs
    (0x3040, 0x309F),   # Hiragana
    (0x30A0, 0x30FF),   # Katakana
)


# Bump this whenever tokenize()'s output changes for the same input (new
# segmentation rule, new normalization step, etc.). _index_stale() compares
# it against what's stored in the index's index_meta table and forces a
# rebuild on mismatch — otherwise an index built by an older tokenizer keeps
# serving content that new query tokens can never match (silently, since
# _index_stale()'s mtime check alone doesn't notice: no atom file changed,
# only the code that tokenizes them did).
TOKENIZER_VERSION = 2


def _is_cjk(ch: str) -> bool:
    cp = ord(ch)
    return any(lo <= cp <= hi for lo, hi in _CJK_RANGES)


def _normalize(text: str) -> str:
    return unicodedata.normalize("NFKC", text).lower()


def tokenize(query: str) -> list[str]:
    """Unicode-aware tokenizer: NFKC-normalize, lowercase, segment on \\w+.

    Whitespace-delimited scripts (Latin, Cyrillic, Devanagari, Arabic, ...)
    come out as whole words, same as before. CJK runs have no whitespace to
    segment on, so a bare \\w+ would swallow an entire sentence into one
    unmatchable token — those get overlapping character bigrams instead.

    # ponytail: Python's \\w excludes standalone combining marks (category
    # Mn/Mc), so scripts that stack vowel signs onto a base letter (Devanagari
    # matras, Arabic harakat) can fragment one word into several short tokens
    # at each mark boundary. Retrieval still round-trips (index and query go
    # through this same fragmentation), just with coarser word boundaries.
    # Upgrade path: swap in the third-party `regex` module's \\p{L}\\p{M}*
    # pattern if that dependency is ever acceptable here.
    """
    normalized = _normalize(query)
    tokens: list[str] = []
    for word in re.findall(r"\w+", normalized, flags=re.UNICODE):
        if all(_is_cjk(ch) for ch in word):
            if len(word) == 1:
                tokens.append(word)
            else:
                tokens.extend(word[i:i + 2] for i in range(len(word) - 1))
        else:
            tokens.append(word)
    return tokens


def search_atoms(
    root: Path | str,
    query: str,
    *,
    limit: int = 10,
    atom_type: str | None = None,
    status: str | None = None,
    as_of: str | None = None,
    expand: bool = True,
) -> dict[str, Any]:
    """Search atoms, bi-temporally ranked and optionally supplemented by a
    deterministic query expansion.

    ``as_of`` is the bi-temporal ranking reference time (default: now) — see
    shiroe.memory.bitemporal.rank_key. Current/valid atoms outrank superseded
    or not-yet/no-longer-valid ones; it does not filter results out, it only
    orders them (a superseded atom can still fill a slot when there aren't
    enough current matches).

    Expansion (see shiroe.memory.expand) only ever *supplements*: direct-token
    results are computed and bi-temporally ranked first, and are never
    reordered or dropped by expansion, so a query that already gets full,
    correct results behaves identically whether expand is True or False.
    Expansion only fills remaining slots up to `limit` when the direct
    search comes up short -- and it never runs at all when the query itself
    didn't tokenize (see the abstention check below), so it can never turn
    an honest abstention into a fabricated match.
    """
    root_path = Path(root)
    db_path = root_path / INDEX_PATH
    tokens = tokenize(query)
    if not tokens:
        return {
            "query": query,
            "tokens": tokens,
            "source": "jsonl",
            "abstained": True,
            "matches": [],
            "expansion": {"tokens": [], "added": []},
        }

    expansion = expand_tokens(tokens) if expand else {"tokens": [], "added": []}

    if db_path.exists() and not _index_stale(root_path, db_path):
        try:
            result = _search_sqlite(db_path, query, tokens, expansion, limit, atom_type, status, as_of)
            result["expansion"] = expansion
            return result
        except sqlite3.Error:
            pass
    result = _search_jsonl(root_path, query, tokens, expansion, limit, atom_type, status, as_of)
    result["expansion"] = expansion
    return result


def _index_stale(root: Path, db_path: Path) -> bool:
    """True when any atom file changed at/after the index was built, or the
    index was built by a different tokenizer version.

    Guarantees add -> search coherence: a freshly appended atom is never
    hidden behind a stale SQLite index; we fall back to the canonical JSONL
    scan until `shiroe memory index` rebuilds it. The tokenizer-version check
    covers the upgrade case the mtime check can't see: an index built before
    a tokenizer change still has an up-to-date mtime (no atom file changed),
    but its FTS content was tokenized the old way and new query tokens
    (e.g. CJK bigrams) will never match it.
    """
    try:
        index_mtime = db_path.stat().st_mtime
    except OSError:
        return True
    if _stored_tokenizer_version(db_path) != TOKENIZER_VERSION:
        return True
    atom_dir = root / "memory" / "l1_atoms"
    if not atom_dir.exists():
        return False
    for path in atom_dir.glob("*.jsonl"):
        try:
            if path.stat().st_mtime >= index_mtime:
                return True
        except OSError:
            continue
    return False


def _stored_tokenizer_version(db_path: Path) -> int | None:
    """Version recorded in index_meta at build time, or None if absent —
    covers both a pre-upgrade index (no index_meta table at all) and a
    fresh-but-differently-versioned one.
    """
    try:
        conn = sqlite3.connect(db_path)
        try:
            row = conn.execute(
                "SELECT value FROM index_meta WHERE key = 'tokenizer_version'"
            ).fetchone()
        finally:
            conn.close()
    except sqlite3.Error:
        return None
    return int(row[0]) if row else None


def _fts_query(
    conn: sqlite3.Connection,
    match_terms: list[str],
    atom_type: str | None,
    status: str | None,
    exclude_ids: set[str],
    limit: int,
) -> list[tuple[Any, ...]]:
    # Tokens are quoted as FTS5 string literals so an unlucky token can never
    # be parsed as a MATCH operator (NEAR, column filters, etc.) or unbalance
    # the query — belt-and-braces on top of tokens already being restricted
    # to \w+ output.
    match_query = " OR ".join('"' + token.replace('"', '""') + '"' for token in match_terms)
    filters = []
    params: list[Any] = [match_query]
    if atom_type:
        filters.append("atoms.type = ?")
        params.append(atom_type)
    if status:
        filters.append("atoms.status = ?")
        params.append(status)
    if exclude_ids:
        filters.append(f"atoms.id NOT IN ({','.join('?' for _ in exclude_ids)})")
        params.extend(sorted(exclude_ids))
    where = " AND " + " AND ".join(filters) if filters else ""
    params.append(limit)
    sql = f"""
        SELECT atoms.raw_json, bm25(atoms_fts) AS rank
        FROM atoms_fts
        JOIN atoms ON atoms_fts.id = atoms.id
        WHERE atoms_fts MATCH ?{where}
        ORDER BY rank
        LIMIT ?
    """
    return conn.execute(sql, params).fetchall()


def _rank_and_trim(
    candidates: list[dict[str, Any]],
    as_of: str | None,
    limit: int,
) -> list[dict[str, Any]]:
    """Bi-temporal-first sort (current/valid outranks superseded/expired) --
    see shiroe.memory.bitemporal.rank_key. Relevance (`rank_position`, the
    FTS rank order) comes next, then recency breaks any remaining tie.
    Recency must sit after relevance: it's a continuous value that almost
    never ties, so putting it first would let recency decide every
    comparison before relevance was ever consulted -- see
    shiroe.memory.bitemporal.recency_key. Shared by the direct and expansion
    passes so a superseded atom matched only via expansion still can't
    outrank a current expansion match.
    """
    candidates.sort(
        key=lambda item: (
            *rank_key(item["atom"], as_of),
            item["rank_position"],
            recency_key(item["atom"]),
        )
    )
    return [{k: v for k, v in item.items() if k != "rank_position"} for item in candidates[:limit]]


def _search_sqlite(
    db_path: Path,
    query: str,
    tokens: list[str],
    expansion: dict[str, Any],
    limit: int,
    atom_type: str | None,
    status: str | None,
    as_of: str | None = None,
) -> dict[str, Any]:
    conn = sqlite3.connect(db_path)
    try:
        # ponytail: over-fetch a bounded window (not the full match set) so
        # the bitemporal tie-break has candidates to re-rank within — a
        # superseded fact ranked just outside `limit` by bm25 alone can
        # still lose to a current one inside it. Ceiling: a superseded fact
        # ranked beyond the window is still invisible to the tie-break;
        # raise the multiplier if that proves visible in practice.
        rows = _fts_query(conn, tokens, atom_type, status, set(), min(limit * 4, 200))
        direct = []
        for position, row in enumerate(rows):
            atom = json.loads(row[0])
            direct.append({
                "atom": atom,
                "score": round(float(row[1]), 6),
                "matched_via": "direct",
                "why": _why(atom, tokens, "SQLite FTS rank"),
                "rank_position": position,
            })
        matches = _rank_and_trim(direct, as_of, limit)

        # Supplement only: direct matches above are never reordered or
        # dropped further. Expansion terms just fill remaining slots when
        # the direct search came up short, and only atoms not already
        # matched directly are eligible, so a query that already fills
        # `limit` behaves identically whether expansion ran or not.
        remaining = limit - len(matches)
        if remaining > 0 and expansion["tokens"]:
            exclude_ids = {m["atom"]["id"] for m in matches}
            extra_rows = _fts_query(
                conn, expansion["tokens"], atom_type, status, exclude_ids, min(remaining * 4, 200)
            )
            extra = []
            for position, row in enumerate(extra_rows):
                atom = json.loads(row[0])
                extra.append({
                    "atom": atom,
                    "score": round(float(row[1]), 6),
                    "matched_via": "expansion",
                    "why": _why(atom, expansion["tokens"], "SQLite FTS rank (expansion)"),
                    "rank_position": position,
                })
            matches.extend(_rank_and_trim(extra, as_of, remaining))
    finally:
        conn.close()
    return {
        "query": query,
        "tokens": tokens,
        "source": "sqlite",
        "abstained": False,
        "matches": matches,
    }


def _search_jsonl(
    root: Path,
    query: str,
    tokens: list[str],
    expansion: dict[str, Any],
    limit: int,
    atom_type: str | None,
    status: str | None,
    as_of: str | None = None,
) -> dict[str, Any]:
    atoms = AtomStore(root).load(atom_type=atom_type, status=status)
    direct_scores, _ = _score_corpus(atoms, tokens)
    scored = []
    for atom in atoms:
        score = direct_scores.get(atom["id"], 0.0)
        if score > 0:
            scored.append({
                "atom": atom,
                "score": score,
                "matched_via": "direct",
                "why": _why(atom, tokens, "JSONL BM25 scan"),
            })
    # Bi-temporal validity/supersession outranks raw text score (a superseded
    # or not-yet/no-longer-valid fact must not outrank a current one just
    # because it happens to match the query text better) — see
    # shiroe.memory.bitemporal.rank_key. Score is next: among atoms that are
    # equally valid and current, relevance decides. Only then does recency
    # break ties, followed by created_at and id for a total order.
    scored.sort(
        key=lambda item: (
            *rank_key(item["atom"], as_of),
            -item["score"],
            recency_key(item["atom"]),
            item["atom"]["created_at"],
            item["atom"]["id"],
        )
    )
    matches = scored[:limit]

    # Same supplement-only rule as the SQLite path: fill remaining slots
    # from expansion terms, excluding atoms already present, never touching
    # the direct-match ordering above.
    remaining = limit - len(matches)
    if remaining > 0 and expansion["tokens"]:
        exclude_ids = {m["atom"]["id"] for m in matches}
        expansion_scores, _ = _score_corpus(atoms, expansion["tokens"])
        extra = []
        for atom in atoms:
            if atom["id"] in exclude_ids:
                continue
            score = expansion_scores.get(atom["id"], 0.0)
            if score > 0:
                extra.append({
                    "atom": atom,
                    "score": score,
                    "matched_via": "expansion",
                    "why": _why(atom, expansion["tokens"], "JSONL BM25 scan (expansion)"),
                })
        # Same dominance -> relevance -> recency -> stable-tiebreaker order
        # as the direct-match sort above -- see bitemporal.rank_key and
        # bitemporal.recency_key.
        extra.sort(
            key=lambda item: (
                *rank_key(item["atom"], as_of),
                -item["score"],
                recency_key(item["atom"]),
                item["atom"]["created_at"],
                item["atom"]["id"],
            )
        )
        matches.extend(extra[:remaining])

    return {
        "query": query,
        "tokens": tokens,
        "source": "jsonl",
        "abstained": False,
        "matches": matches,
    }


# Okapi BM25 parameters. Same values the SQLite FTS5 path uses internally and
# the same the bm25 benchmark baseline uses, so the two retrieval paths are
# comparable to each other and to the baseline.
_BM25_K1 = 1.5
_BM25_B = 0.75


def _atom_terms(atom: dict[str, Any]) -> list[str]:
    """Word-level terms for an atom, tokenized exactly like the query.

    Tokens are already NFKC-normalized (via tokenize()); running the atom
    text through the same tokenizer keeps query and document in one term
    space, including the CJK bigram handling.
    """
    return tokenize(" ".join([
        atom.get("claim", ""),
        atom.get("summary", ""),
        atom.get("source", ""),
        " ".join(str(tag) for tag in atom.get("tags", [])),
    ]))


def _score_corpus(
    atoms: list[dict[str, Any]], tokens: list[str],
) -> tuple[dict[str, float], dict[str, list[str]]]:
    """Okapi BM25 over the whole loaded corpus.

    This used to be `sum(haystack.count(token) for token in tokens)` -- a raw
    substring occurrence count. Three things were wrong with it, and all three
    push ranking the wrong way on real corpora:

    - **No IDF.** A term appearing in every atom counted as much as the one
      rare term that actually identifies the answer, so common words drowned
      out the discriminating one.
    - **No length normalization and no term-frequency saturation.** Score grew
      without bound with document length, so a long atom won by repetition
      alone.
    - **Substring, not word, matching.** `haystack.count("cat")` also matched
      inside "category" and "concatenate".

    It also double-counted: `summary` is conventionally a prefix of `claim`,
    so a hit in the first ~200 characters scored twice.

    The corpus is already fully loaded by `_search_jsonl`, so document
    frequency and average length are free here -- no index, no extra pass over
    storage.

    Returns (score by atom id, terms by atom id); the terms are reused by
    `_why` so the explanation reflects what was actually scored.
    """
    terms_by_id: dict[str, list[str]] = {a["id"]: _atom_terms(a) for a in atoms}
    n_docs = len(atoms)
    if n_docs == 0:
        return {}, terms_by_id

    lengths = {aid: len(t) or 1 for aid, t in terms_by_id.items()}
    avg_len = sum(lengths.values()) / n_docs

    # Document frequency per query term, computed once for the whole corpus.
    doc_freq: dict[str, int] = {}
    for term in set(tokens):
        doc_freq[term] = sum(1 for t in terms_by_id.values() if term in t)

    scores: dict[str, float] = {}
    for atom in atoms:
        aid = atom["id"]
        terms = terms_by_id[aid]
        doc_len = lengths[aid]
        score = 0.0
        for term in tokens:
            df = doc_freq.get(term, 0)
            if df == 0:
                continue
            tf = terms.count(term)
            if tf == 0:
                continue
            idf = math.log((n_docs - df + 0.5) / (df + 0.5) + 1)
            denom = tf + _BM25_K1 * (1 - _BM25_B + _BM25_B * doc_len / avg_len)
            score += idf * (tf * (_BM25_K1 + 1)) / denom
        if score > 0:
            scores[aid] = score
    return scores, terms_by_id


def _why(atom: dict[str, Any], tokens: list[str], method: str) -> str:
    fields = []
    for field in ("claim", "summary", "source"):
        text = _normalize(str(atom.get(field, "")))
        if any(token in text for token in tokens):
            fields.append(field)
    return f"{method}; matched fields: {', '.join(fields) if fields else 'none'}"
