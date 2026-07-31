"""Unicode-aware retrieval — tokenizer coverage, fail-open regression, and
round-trip recall across scripts on both the SQLite FTS and JSONL paths.

Refs SHR-65.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from shiroe.memory.atom_store import AtomStore
from shiroe.memory.indexer import INDEX_PATH, rebuild_index
from shiroe.memory.schemas import create_atom
from shiroe.memory.search import _index_stale, search_atoms, tokenize


# ---------------------------------------------------------------------------
# tokenize()
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "query",
    [
        "你好世界",           # Chinese, no whitespace
        "モデルルーティング",   # Japanese katakana, no whitespace
        "नमस्ते दुनिया",       # Hindi, Devanagari
        "مرحبا بالعالم",       # Arabic
    ],
)
def test_tokenize_non_ascii_scripts_are_not_empty(query: str) -> None:
    assert tokenize(query) != []


def test_tokenize_accented_french_keeps_whole_words() -> None:
    # The old ASCII-only regex stripped accented letters entirely, turning
    # "résumé café" into fragments of the leftover ASCII runs.
    assert tokenize("résumé café") == ["résumé", "café"]


def test_tokenize_plain_english_unchanged() -> None:
    assert tokenize("model routing") == ["model", "routing"]


def test_tokenize_cjk_produces_overlapping_bigrams() -> None:
    # A whitespace-free CJK run must not collapse into one giant token —
    # that's exactly what made it unmatchable via FTS/substring search.
    assert tokenize("你好世界") == ["你好", "好世", "世界"]


def test_tokenize_truly_untokenizable_query_is_empty() -> None:
    # Punctuation/emoji-only input has no \w+ runs at all.
    assert tokenize("!!!") == []
    assert tokenize("🎉🎉🎉") == []


# ---------------------------------------------------------------------------
# Abstention regression (search.py:121 fail-open bug)
# ---------------------------------------------------------------------------

def _fact(claim: str, provenance: str) -> dict:
    return create_atom(
        atom_type="fact",
        claim=claim,
        summary=claim,
        source="manual:test-retrieval-unicode",
        provenance=provenance,
    )


def test_untokenizable_query_abstains_instead_of_returning_everything(tmp_path: Path) -> None:
    """Regression for the fail-open bug: `if score > 0 or not tokens` meant an
    empty token list matched EVERY atom. A query that produces zero tokens
    must return zero matches, and the caller must be able to tell that apart
    from a real search that legitimately found nothing.
    """
    store = AtomStore(tmp_path)
    atom_a = store.append(_fact("Kubernetes migration owner is the platform team", "p1"))
    atom_b = store.append(_fact("Coffee machine is broken on floor 3", "p2"))

    result = search_atoms(tmp_path, "!!!")

    assert result["tokens"] == []
    assert result["abstained"] is True
    assert result["matches"] == []
    ids = {m["atom"]["id"] for m in result["matches"]}
    assert atom_a["id"] not in ids
    assert atom_b["id"] not in ids


def test_real_search_with_no_hits_is_not_marked_abstained(tmp_path: Path) -> None:
    store = AtomStore(tmp_path)
    store.append(_fact("Kubernetes migration owner is the platform team", "p1"))

    result = search_atoms(tmp_path, "spreadsheet formula")

    assert result["tokens"] != []
    assert result["abstained"] is False
    assert result["matches"] == []


# ---------------------------------------------------------------------------
# Round-trip recall by script, both retrieval paths
# ---------------------------------------------------------------------------

SCRIPT_FIXTURES = [
    ("chinese", "你好世界是一个问候语", "你好世界"),
    ("japanese", "モデルルーティングの設定について", "モデルルーティング"),
    ("hindi", "नमस्ते दुनिया एक अभिवादन है", "नमस्ते"),
    ("arabic", "مرحبا بالعالم تحية عربية", "مرحبا"),
    ("french", "résumé café discussion notes", "résumé café"),
    ("english", "Kubernetes migration owner is the platform team", "Kubernetes migration"),
]


def _ingest_fixtures(root: Path) -> dict[str, dict]:
    store = AtomStore(root)
    atoms = {}
    for label, claim, _query in SCRIPT_FIXTURES:
        atoms[label] = store.append(_fact(claim, provenance=label))
    return atoms


def test_round_trip_recall_jsonl_fallback(tmp_path: Path) -> None:
    """No SQLite index built -> search_atoms must use the JSONL path."""
    atoms = _ingest_fixtures(tmp_path)
    misses = []
    for label, _claim, query in SCRIPT_FIXTURES:
        result = search_atoms(tmp_path, query)
        assert result["source"] == "jsonl"
        ids = {m["atom"]["id"] for m in result["matches"]}
        if atoms[label]["id"] not in ids:
            misses.append(label)
    recall = (len(SCRIPT_FIXTURES) - len(misses)) / len(SCRIPT_FIXTURES)
    print(f"\n[jsonl] recall by script: {recall:.0%}, misses={misses}")
    assert not misses, f"jsonl fallback missed: {misses}"


def test_round_trip_recall_sqlite_fts(tmp_path: Path) -> None:
    """SQLite index built and fresh -> search_atoms must use the sqlite path."""
    atoms = _ingest_fixtures(tmp_path)
    rebuild_index(tmp_path)
    misses = []
    for label, _claim, query in SCRIPT_FIXTURES:
        result = search_atoms(tmp_path, query)
        assert result["source"] == "sqlite"
        ids = {m["atom"]["id"] for m in result["matches"]}
        if atoms[label]["id"] not in ids:
            misses.append(label)
    recall = (len(SCRIPT_FIXTURES) - len(misses)) / len(SCRIPT_FIXTURES)
    print(f"\n[sqlite] recall by script: {recall:.0%}, misses={misses}")
    assert not misses, f"sqlite FTS missed: {misses}"


# ---------------------------------------------------------------------------
# Tokenizer-version staleness: an index built by an old (raw-text) tokenizer
# must not be served to a query producing new-style tokens (e.g. CJK
# bigrams) — that mismatch returns zero results silently, with no error and
# no atom-file mtime change to trip the existing staleness check.
# ---------------------------------------------------------------------------

def test_index_missing_tokenizer_version_is_stale_and_falls_back(tmp_path: Path) -> None:
    atoms = _ingest_fixtures(tmp_path)
    rebuild_index(tmp_path)
    db_path = tmp_path / INDEX_PATH
    assert _index_stale(tmp_path, db_path) is False

    # Simulate a pre-upgrade install: an index built before index_meta
    # existed at all (the exact shape of an old raw-text index).
    conn = sqlite3.connect(db_path)
    conn.execute("DROP TABLE index_meta")
    conn.commit()
    conn.close()

    assert _index_stale(tmp_path, db_path) is True

    _label, _claim, query = next(f for f in SCRIPT_FIXTURES if f[0] == "chinese")
    result = search_atoms(tmp_path, query)
    assert result["source"] == "jsonl", "stale index must fall back, not serve mismatched FTS content"
    ids = {m["atom"]["id"] for m in result["matches"]}
    assert atoms["chinese"]["id"] in ids


def test_index_old_tokenizer_version_is_stale_and_falls_back(tmp_path: Path) -> None:
    atoms = _ingest_fixtures(tmp_path)
    rebuild_index(tmp_path)
    db_path = tmp_path / INDEX_PATH

    conn = sqlite3.connect(db_path)
    conn.execute("UPDATE index_meta SET value = '1' WHERE key = 'tokenizer_version'")
    conn.commit()
    conn.close()

    assert _index_stale(tmp_path, db_path) is True

    _label, _claim, query = next(f for f in SCRIPT_FIXTURES if f[0] == "chinese")
    result = search_atoms(tmp_path, query)
    assert result["source"] == "jsonl"
    ids = {m["atom"]["id"] for m in result["matches"]}
    assert atoms["chinese"]["id"] in ids
