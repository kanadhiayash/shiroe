"""Okapi BM25 lexical baseline (pure stdlib, no dependencies).

A memory engine that cannot beat a ~40-line BM25 ranker on recall has no
business claiming benchmark superiority. Kept separate from
`sqlite_store.SqliteFtsBackend` (which degrades to a LIKE-fallback ranker
when FTS5 isn't compiled in) so the "lexical baseline" arm is always the
same deterministic ranking formula, everywhere.
"""

from __future__ import annotations

import math
import re

_TOKEN_RE = re.compile(r"[a-z0-9]+")

K1 = 1.5   # term-frequency saturation
B = 0.75   # length-normalization strength


def _tokens(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


class Bm25Backend:
    """Implements the harness ingest/recall interface with Okapi BM25."""

    name = "bm25"

    def __init__(self) -> None:
        self._docs: list[tuple[str, list[str]]] = []  # (text, tokens)

    def reset(self) -> None:
        self._docs = []

    def ingest(self, chunk_id: str, text: str) -> None:
        self._docs.append((text, _tokens(text)))

    def recall(self, query: str, k: int = 5) -> list[str]:
        query_tokens = _tokens(query)
        if not query_tokens or not self._docs:
            return []
        n_docs = len(self._docs)
        avg_len = sum(len(toks) for _, toks in self._docs) / n_docs
        doc_freq: dict[str, int] = {}
        for term in set(query_tokens):
            doc_freq[term] = sum(1 for _, toks in self._docs if term in toks)

        scored = []
        for text, toks in self._docs:
            doc_len = len(toks) or 1
            score = 0.0
            for term in query_tokens:
                df = doc_freq.get(term, 0)
                if df == 0:
                    continue
                idf = math.log((n_docs - df + 0.5) / (df + 0.5) + 1)
                tf = toks.count(term)
                denom = tf + K1 * (1 - B + B * doc_len / avg_len)
                score += idf * (tf * (K1 + 1)) / denom if denom else 0.0
            scored.append((score, text))

        scored.sort(key=lambda item: item[0], reverse=True)
        return [text for score, text in scored[:k] if score > 0]
