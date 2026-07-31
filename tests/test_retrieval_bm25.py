"""JSONL retrieval ranks by Okapi BM25 (issue #196).

The JSONL path used to score with `sum(haystack.count(t) for t in tokens)` --
a raw substring occurrence count with no IDF, no length normalization, no
term-frequency saturation, and substring rather than word matching. The
SQLite path meanwhile used FTS5's real `bm25()`, so the two paths ranked the
same corpus by different functions and results changed depending on whether
anyone had run `shiroe memory index`.

Nothing on the ingest path builds that index, so in practice every recall --
`shiroe recall` and the benchmark's shiroe arm alike -- took the JSONL
fallback and got the weaker ranker.

These tests pin the three properties the old scorer lacked, and the agreement
between the two paths.
"""

from __future__ import annotations

from pathlib import Path

from shiroe.memory.atom_store import AtomStore
from shiroe.memory.indexer import rebuild_index
from shiroe.memory.schemas import create_atom
from shiroe.memory.search import search_atoms


def _fact(claim: str, provenance: str) -> dict:
    return create_atom(
        atom_type="fact",
        claim=claim,
        summary=claim,
        source="manual:test-retrieval-bm25",
        provenance=provenance,
    )


def _ids(result: dict) -> list[str]:
    return [m["atom"]["provenance"] for m in result["matches"]]


def test_rare_term_outranks_common_term(tmp_path: Path) -> None:
    """IDF. The old scorer had none, so a term in every document counted as
    much as the one rare term that identifies the answer."""
    store = AtomStore(tmp_path)
    for i in range(12):
        store.append(_fact(f"deployment pipeline runs stage {i}", f"common-{i}"))
    store.append(_fact("deployment pipeline runs kubernetes", "rare"))

    result = search_atoms(tmp_path, "deployment kubernetes", limit=3)
    assert result["source"] == "jsonl"
    assert _ids(result)[0] == "rare"


def test_long_document_does_not_win_on_repetition(tmp_path: Path) -> None:
    """Length normalization + tf saturation. Under a raw count, padding a
    document with repeats of the query term won outright."""
    store = AtomStore(tmp_path)
    store.append(_fact("cache " * 40 + "unrelated filler text here", "long-repeated"))
    store.append(_fact("the cache invalidation policy is documented", "short-relevant"))

    result = search_atoms(tmp_path, "cache invalidation policy", limit=2)
    assert _ids(result)[0] == "short-relevant"


def test_matching_is_word_level_not_substring(tmp_path: Path) -> None:
    """`haystack.count("cat")` also matched "category" and "concatenate"."""
    store = AtomStore(tmp_path)
    store.append(_fact("the category taxonomy concatenates labels", "substring-only"))
    store.append(_fact("the cat sat on the mat", "true-word"))

    result = search_atoms(tmp_path, "cat", limit=5)
    assert _ids(result) == ["true-word"]


def test_summary_duplication_does_not_double_count(tmp_path: Path) -> None:
    """`summary` is conventionally a prefix of `claim`, so the old scorer
    counted a hit in the first ~200 chars twice."""
    store = AtomStore(tmp_path)
    store.append(create_atom(
        atom_type="fact",
        claim="alpha beta gamma",
        summary="alpha beta gamma",
        source="manual:test-retrieval-bm25",
        provenance="dup",
    ))
    store.append(create_atom(
        atom_type="fact",
        claim="alpha beta gamma delta epsilon",
        summary="",
        source="manual:test-retrieval-bm25",
        provenance="nodup",
    ))
    result = search_atoms(tmp_path, "delta", limit=5)
    assert _ids(result) == ["nodup"]


def test_sqlite_and_jsonl_agree_on_the_same_corpus(tmp_path: Path) -> None:
    """The coherence bug: both paths must now rank by BM25, so a corpus
    returns the same top-k whether or not the index was built."""
    store = AtomStore(tmp_path)
    for label, claim in {
        "auth": "the auth service validates bearer tokens",
        "cache": "the cache layer expires entries hourly",
        "queue": "the queue drains into the auth service",
        "db": "the database stores bearer token hashes",
    }.items():
        store.append(_fact(claim, label))

    jsonl = search_atoms(tmp_path, "auth bearer tokens", limit=3)
    assert jsonl["source"] == "jsonl"

    rebuild_index(tmp_path)
    indexed = search_atoms(tmp_path, "auth bearer tokens", limit=3)
    assert indexed["source"] == "sqlite"

    assert _ids(indexed) == _ids(jsonl)


def test_abstention_still_holds(tmp_path: Path) -> None:
    """A query with no matching term must return nothing, not a low-scoring
    everything. BM25 changes ranking, never the decision to abstain."""
    store = AtomStore(tmp_path)
    store.append(_fact("the auth service validates bearer tokens", "auth"))

    result = search_atoms(tmp_path, "helicopter", limit=5)
    assert result["matches"] == []
