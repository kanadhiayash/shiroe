"""
The indexed and unindexed search paths must return the same answers.

`search_atoms` has two backends: an FTS5 index at memory/indexes/shiroe.sqlite,
and a JSONL scan. The scan is not a debug tool -- it is the live fallback, and
it is reached silently in three ways:

    if db_path.exists() and not _index_stale(...):
        try:
            return _search_sqlite(...)
        except sqlite3.Error:
            pass                      # <- corrupt index, no signal
    return _search_jsonl(...)         # <- also: no index, or stale index

So a user's results can change backend without anything being logged or raised.
If the two disagree at the same k, retrieval quality silently depends on whether
an index file happens to exist and happens to be fresh. That is the property
worth pinning, and it is what "equal-k baselines from pinned fixtures" means
here: same corpus, same query, same k, same ordered ids, both ways.

The performance assertion is deliberately a *ceiling*, not a benchmark. Wall
clock on a shared CI runner is noisy, so this asserts an order of magnitude that
a correctness regression would blow through, and nothing tighter.

KNOWN LIMITATION, not fixed here: parity holds while relevance is well
separated, and breaks when a query matches essentially the whole corpus. The two
backends are different ranking functions -- FTS5 computes bm25 from its own
table statistics, `_score_corpus` computes BM25 from the fully loaded corpus --
so they part company once scores bunch up. Closing it means giving the indexed
path the same corpus statistics at build time, which changes the index format
rather than a sort key. Its exact extent is pinned by
`test_backend_divergence_on_a_saturated_query_is_bounded_and_known`.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from shiroe.memory.atom_store import AtomStore
from shiroe.memory.indexer import INDEX_PATH, rebuild_index
from shiroe.memory.schemas import create_atom
from shiroe.memory.search import search_atoms, tokenize


# Pinned corpus. Deterministic, and written so several queries match more than
# one atom -- a corpus where every query has exactly one hit cannot detect an
# ordering disagreement between the backends.
CORPUS = [
    ("sqlite is the canonical current state for shiroe memory", "storage"),
    ("jsonl holds the canonical append-only history of every event", "storage"),
    ("markdown views are generated projections and never canonical", "storage"),
    ("the retrieval index is a rebuildable cache, not canonical state", "retrieval"),
    ("bitemporal ranking prefers current facts over superseded ones", "retrieval"),
    ("contradiction detection compares overlapping valid intervals", "contradiction"),
    ("the canon gate certifies every wave of this program", "process"),
    ("privacy scrubbing runs before any event reaches disk", "privacy"),
    ("event envelopes are hash chained so tampering is detectable", "storage"),
    ("team packs declare how many agents they activate", "process"),
]

QUERIES = [
    "canonical state",
    "jsonl history",
    "retrieval index",
    "contradiction",
    "canonical",
    "event",
    "storage",
    "nonexistent unmatchable term",
]


@pytest.fixture()
def corpus_repo(fake_repo: Path) -> Path:
    store = AtomStore(fake_repo)
    for i, (claim, topic) in enumerate(CORPUS):
        store.append(create_atom(
            atom_type="fact",
            claim=claim,
            summary=f"{topic}: {claim}",
            # Deliberately shares no token with any pinned query. `source` is
            # a scored field, so a value like "manual:retrieval-test" makes the
            # query "retrieval index" match all ten atoms and turns every
            # comparison below into the degenerate all-match case, which is
            # covered on purpose by test_backend_divergence_on_a_saturated_query.
            source="manual:fixture",
            provenance=f"pinned-corpus-{i:02d}",
            recorded_at=f"2026-01-{i + 1:02d}T00:00:00Z",
        ))
    return fake_repo


def _ids(result: dict) -> list[str]:
    """Ordered atom ids. Order is part of the contract, not just membership."""
    return [m["atom"]["id"] for m in result["matches"]]


def _search_without_index(root: Path, query: str, limit: int) -> dict:
    """Force the JSONL path by hiding the index for the duration of the call."""
    db = root / INDEX_PATH
    hidden = db.with_suffix(".hidden")
    db.rename(hidden)
    try:
        return search_atoms(root, query, limit=limit)
    finally:
        hidden.rename(db)


# Measured baseline, not an aspiration. 26 of 32 (query, k) pairs agree exactly;
# these six do not, and each is the same root cause -- see the module docstring.
# Listed rather than summarised so that a change in either direction fails here
# and has to be looked at.
KNOWN_SET_DIVERGENCE = {("canonical", 3)}
KNOWN_ORDER_DIVERGENCE = {
    ("canonical", 5), ("canonical", 10),
    ("storage", 3), ("storage", 5), ("storage", 10),
}


@pytest.mark.parametrize("query", QUERIES)
@pytest.mark.parametrize("k", [1, 3, 5, 10])
def test_indexed_and_scanned_search_agree_at_equal_k(
    corpus_repo: Path, query: str, k: int
) -> None:
    """The fallback must not quietly change what the user gets back.

    Where the two backends do not agree today, the disagreement is pinned
    rather than tolerated: a pair that starts agreeing, or one that starts
    disagreeing, both fail here. Asserting blanket equality would be asserting
    something untrue, and asserting only set equality would quietly accept an
    ordering change the user would notice.
    """
    rebuild_index(corpus_repo)

    indexed = search_atoms(corpus_repo, query, limit=k)
    assert indexed["source"] == "sqlite", (
        f"expected the indexed path, got {indexed['source']!r}; "
        "this test would otherwise compare the scan against itself"
    )

    scanned = _search_without_index(corpus_repo, query, k)
    assert scanned["source"] == "jsonl"

    case = (query, k)
    detail = (
        f"for {query!r} at k={k}:\n  index: {_ids(indexed)}\n  scan:  {_ids(scanned)}"
    )

    if case in KNOWN_SET_DIVERGENCE:
        assert set(_ids(indexed)) != set(_ids(scanned)), (
            f"known SET divergence no longer reproduces {detail}\n"
            "If this was fixed, remove the pair from KNOWN_SET_DIVERGENCE."
        )
    elif case in KNOWN_ORDER_DIVERGENCE:
        assert set(_ids(indexed)) == set(_ids(scanned)), (
            f"a known ORDER divergence became a SET divergence {detail}"
        )
        assert _ids(indexed) != _ids(scanned), (
            f"known ORDER divergence no longer reproduces {detail}\n"
            "If this was fixed, remove the pair from KNOWN_ORDER_DIVERGENCE."
        )
    else:
        assert _ids(indexed) == _ids(scanned), f"backends disagree {detail}"


def test_abstention_is_identical_on_both_paths(corpus_repo: Path) -> None:
    """An honest empty answer must not become a match by changing backend."""
    rebuild_index(corpus_repo)
    query = "nonexistent unmatchable term"

    indexed = search_atoms(corpus_repo, query, limit=5)
    scanned = _search_without_index(corpus_repo, query, 5)

    assert _ids(indexed) == _ids(scanned) == []


def test_a_corrupt_index_does_not_change_the_answers(corpus_repo: Path) -> None:
    """The silent `except sqlite3.Error: pass` fallback must be answer-preserving.

    Corruption is reached with no log and no raise, so the only thing standing
    between it and wrong results is the two backends agreeing.
    """
    rebuild_index(corpus_repo)
    expected = {q: _ids(search_atoms(corpus_repo, q, limit=5)) for q in QUERIES}

    (corpus_repo / INDEX_PATH).write_bytes(b"this is not a sqlite database")

    changed = []
    for query, ids in expected.items():
        result = search_atoms(corpus_repo, query, limit=5)
        assert result["source"] == "jsonl", "corruption must fall back, not raise"
        if _ids(result) != ids:
            changed.append(query)

    # Same root cause as the divergence pinned above: falling back swaps ranking
    # function. Corruption is silent (`except sqlite3.Error: pass`), so the blast
    # radius is worth stating exactly rather than leaving to inference.
    assert changed == ["canonical", "storage"], (
        f"corrupt-index blast radius changed: results moved for {changed}, "
        "previously ['canonical', 'storage']"
    )


def test_stale_index_is_detected_rather_than_trusted(corpus_repo: Path) -> None:
    """A new atom must be findable even before the index is rebuilt."""
    rebuild_index(corpus_repo)
    store = AtomStore(corpus_repo)
    store.append(create_atom(
        atom_type="fact",
        claim="quokka telemetry arrived after the index was built",
        summary="freshness probe",
        source="manual:retrieval-test",
        provenance="freshness-probe",
    ))

    result = search_atoms(corpus_repo, "quokka telemetry", limit=5)
    assert _ids(result), "a post-index atom was invisible; staleness went undetected"
    assert result["source"] == "jsonl", "a stale index should not be trusted"


def test_indexed_search_stays_within_its_ceiling(corpus_repo: Path) -> None:
    """A ceiling, not a benchmark: wall clock on shared CI is noisy.

    This catches a correctness regression that turns the indexed path into a
    full scan per query, which is the failure mode worth having a bound for.
    """
    rebuild_index(corpus_repo)
    # Warm any lazy import/connection cost so it is not attributed to the query.
    search_atoms(corpus_repo, "canonical", limit=5)

    start = time.perf_counter()
    for _ in range(20):
        for query in QUERIES:
            search_atoms(corpus_repo, query, limit=5)
    elapsed = time.perf_counter() - start

    budget = 10.0
    assert elapsed < budget, (
        f"{20 * len(QUERIES)} indexed searches took {elapsed:.2f}s, "
        f"over the {budget}s ceiling"
    )


def test_tokenizer_version_change_invalidates_the_index(corpus_repo: Path, monkeypatch) -> None:
    """The index stores the tokenizer it was built with, and must distrust another.

    Tokens written by one tokenizer are not comparable to queries tokenized by
    the next; without this the index returns confidently wrong results after an
    upgrade.
    """
    from shiroe.memory import search as search_mod

    rebuild_index(corpus_repo)
    assert search_atoms(corpus_repo, "canonical state", limit=5)["source"] == "sqlite"

    monkeypatch.setattr(search_mod, "TOKENIZER_VERSION", search_mod.TOKENIZER_VERSION + 1)
    assert search_atoms(corpus_repo, "canonical state", limit=5)["source"] == "jsonl", (
        "index built by a different tokenizer was still trusted"
    )


def test_index_is_rebuildable_and_never_canonical(corpus_repo: Path) -> None:
    """Deleting the index must lose nothing: it is a cache, per ADR-0001."""
    rebuild_index(corpus_repo)
    before = {q: _ids(search_atoms(corpus_repo, q, limit=5)) for q in QUERIES}

    (corpus_repo / INDEX_PATH).unlink()
    rebuild_index(corpus_repo)

    after = {q: _ids(search_atoms(corpus_repo, q, limit=5)) for q in QUERIES}
    assert after == before, "rebuilding the index changed the answers"


def test_backend_divergence_on_a_saturated_query_is_bounded_and_known(
    fake_repo: Path,
) -> None:
    """A KNOWN, UNFIXED divergence, pinned so it cannot widen unnoticed.

    When a query matches essentially the whole corpus, the two backends stop
    agreeing -- and they disagree on membership, not merely order, so a user
    gets different results depending on whether an index file exists.

    The cause is that they are different ranking functions. FTS5 computes bm25
    from the statistics of its own table; `_score_corpus` computes BM25 from the
    fully loaded corpus. They coincide while relevance is well separated and
    part company once it is not. Closing it properly means giving the indexed
    path the same corpus statistics -- document frequency, average length, N --
    at build time, which is a change to the index format, not to a sort key.

    This test does not assert the divergence is acceptable. It records exactly
    how far it goes today, so the follow-up has a baseline and any regression
    that makes it worse fails here.
    """
    store = AtomStore(fake_repo)
    for i, (claim, topic) in enumerate(CORPUS):
        store.append(create_atom(
            atom_type="fact",
            claim=claim,
            summary=f"{topic}: {claim}",
            source="manual:retrieval-test",  # collides with the query below
            provenance=f"saturated-{i:02d}",
            recorded_at=f"2026-01-{i + 1:02d}T00:00:00Z",
        ))
    rebuild_index(fake_repo)

    disagreed = []
    for k in (1, 3, 5, 10):
        indexed = _ids(search_atoms(fake_repo, "retrieval index", limit=k))
        scanned = _ids(_search_without_index(fake_repo, "retrieval index", k))
        if indexed != scanned:
            disagreed.append(k)

    assert disagreed, (
        "the saturated-query divergence appears to be fixed -- delete this test "
        "and drop the known-limitation note from the module docstring"
    )
    assert disagreed == [5, 10], (
        f"backend divergence changed shape: disagrees at k={disagreed}, "
        "previously k=[5, 10]"
    )
    # k=1 and k=3 still agree: the best matches stay well separated even here.
    assert 1 not in disagreed, "divergence has spread to the top-1 result"


def test_every_pinned_query_tokenizes(corpus_repo: Path) -> None:
    """Guard the fixtures themselves: an untokenizable query abstains early.

    Without this a typo in QUERIES would make the parity tests above compare two
    empty lists and pass while proving nothing.
    """
    matching = [q for q in QUERIES if tokenize(q)]
    assert matching == QUERIES, "a pinned query does not tokenize"

    rebuild_index(corpus_repo)
    hits = {q: len(_ids(search_atoms(corpus_repo, q, limit=10))) for q in QUERIES}
    assert sum(1 for q, n in hits.items() if n > 1) >= 3, (
        f"pinned corpus is too sparse to detect an ordering disagreement: {hits}"
    )
