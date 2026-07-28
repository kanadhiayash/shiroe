"""Deterministic atom search with SQLite FTS and JSONL fallback."""

from __future__ import annotations

import json
import re
import sqlite3
import unicodedata
from pathlib import Path
from typing import Any

from zeref.memory.atom_store import AtomStore
from zeref.memory.indexer import INDEX_PATH


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
) -> dict[str, Any]:
    root_path = Path(root)
    db_path = root_path / INDEX_PATH
    tokens = tokenize(query)
    if db_path.exists() and tokens and not _index_stale(root_path, db_path):
        try:
            return _search_sqlite(db_path, query, tokens, limit, atom_type, status)
        except sqlite3.Error:
            pass
    return _search_jsonl(root_path, query, tokens, limit, atom_type, status)


def _index_stale(root: Path, db_path: Path) -> bool:
    """True when any atom file changed at/after the index was built, or the
    index was built by a different tokenizer version.

    Guarantees add -> search coherence: a freshly appended atom is never
    hidden behind a stale SQLite index; we fall back to the canonical JSONL
    scan until `zeref memory index` rebuilds it. The tokenizer-version check
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


def _search_sqlite(
    db_path: Path,
    query: str,
    tokens: list[str],
    limit: int,
    atom_type: str | None,
    status: str | None,
) -> dict[str, Any]:
    # Tokens are quoted as FTS5 string literals so an unlucky token can never
    # be parsed as a MATCH operator (NEAR, column filters, etc.) or unbalance
    # the query — belt-and-braces on top of tokens already being restricted
    # to \w+ output.
    match_query = " OR ".join('"' + token.replace('"', '""') + '"' for token in tokens)
    filters = []
    params: list[Any] = [match_query]
    if atom_type:
        filters.append("atoms.type = ?")
        params.append(atom_type)
    if status:
        filters.append("atoms.status = ?")
        params.append(status)
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
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()
    matches = []
    for row in rows:
        atom = json.loads(row[0])
        matches.append({
            "atom": atom,
            "score": round(float(row[1]), 6),
            "why": _why(atom, tokens, "SQLite FTS rank"),
        })
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
    limit: int,
    atom_type: str | None,
    status: str | None,
) -> dict[str, Any]:
    # No tokens means the query couldn't be tokenized (or was blank) — abstain
    # rather than fail open into "every atom matches". `abstained: True` lets
    # a caller tell this apart from a real, tokenized search that found
    # nothing (`abstained: False`, `matches: []`).
    if not tokens:
        return {
            "query": query,
            "tokens": tokens,
            "source": "jsonl",
            "abstained": True,
            "matches": [],
        }
    atoms = AtomStore(root).load(atom_type=atom_type, status=status)
    scored = []
    for atom in atoms:
        score = _score_atom(atom, tokens)
        if score > 0:
            scored.append({
                "atom": atom,
                "score": score,
                "why": _why(atom, tokens, "JSONL token scan"),
            })
    scored.sort(key=lambda item: (-item["score"], item["atom"]["created_at"], item["atom"]["id"]))
    return {
        "query": query,
        "tokens": tokens,
        "source": "jsonl",
        "abstained": False,
        "matches": scored[:limit],
    }


def _score_atom(atom: dict[str, Any], tokens: list[str]) -> int:
    # Tokens are already NFKC-normalized (via tokenize()); normalize the
    # haystack the same way so e.g. a precomposed vs. combining-mark "é"
    # in stored text still substring-matches the query.
    haystack = _normalize(" ".join([
        atom.get("claim", ""),
        atom.get("summary", ""),
        atom.get("source", ""),
        " ".join(str(tag) for tag in atom.get("tags", [])),
    ]))
    return sum(haystack.count(token) for token in tokens)


def _why(atom: dict[str, Any], tokens: list[str], method: str) -> str:
    fields = []
    for field in ("claim", "summary", "source"):
        text = _normalize(str(atom.get(field, "")))
        if any(token in text for token in tokens):
            fields.append(field)
    return f"{method}; matched fields: {', '.join(fields) if fields else 'none'}"
