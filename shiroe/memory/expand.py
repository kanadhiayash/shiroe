"""Deterministic, inspectable query expansion over tokenize() output.

Shiroe's retrieval story only holds together if every match is explainable —
a black-box expansion (embeddings, an LLM call, a hidden synonym service)
would break that guarantee even if it improved recall. So expansion here is:

- Deterministic: same input tokens always produce the same expansion, no
  external state, no randomness.
- Inspectable: expand_tokens() returns exactly which terms were added and
  why (stemmed from X / synonym of X), not just a bigger token bag.
- Additive only: callers use this to *supplement* a direct-token search
  when it comes up short, never to replace or reorder direct matches. See
  search.py's search_atoms() for how the supplement is applied.

No dependency: suffix-stripping stemmer + a small curated synonym map, both
plain Python.
"""

from __future__ import annotations

from typing import Any


# Ordered longest-suffix-first so "policies" hits the "ies" rule before a
# shorter, wronger one could apply. Each stem must stay at least
# _MIN_STEM_LEN characters, or we skip stemming that token entirely --
# short words lose too much meaning when you lop off a suffix ("as" -/-> "a").
_SUFFIX_RULES: tuple[tuple[str, str], ...] = (
    ("ies", "y"),   # policies -> policy
    ("ied", "y"),   # studied -> study
    ("ing", ""),    # routing -> rout
    ("ed", ""),     # deployed -> deploy
    ("es", ""),     # matches -> match
    ("s", ""),      # models -> model
)
_MIN_STEM_LEN = 3

# Small curated synonym map. Deliberately short: every entry is a real,
# unambiguous near-synonym pair a human reviewer can sanity-check at a
# glance. Grow it by editing this dict, never by wiring in a thesaurus API.
SYNONYMS: dict[str, tuple[str, ...]] = {
    "bug": ("defect", "issue"),
    "defect": ("bug", "issue"),
    "issue": ("bug", "problem"),
    "problem": ("issue", "bug"),
    "error": ("failure", "fault"),
    "failure": ("error", "fault"),
    "fast": ("quick", "rapid"),
    "quick": ("fast", "rapid"),
    "start": ("begin", "launch"),
    "begin": ("start", "launch"),
    "stop": ("halt", "end"),
    "halt": ("stop", "end"),
    "delete": ("remove", "erase"),
    "remove": ("delete", "erase"),
    "update": ("modify", "change"),
    "modify": ("update", "change"),
    "config": ("configuration", "settings"),
    "configuration": ("config", "settings"),
    "owner": ("lead", "maintainer"),
    "maintainer": ("owner", "lead"),
    "docs": ("documentation",),
    "documentation": ("docs",),
    "broken": ("failing", "down"),
    "failing": ("broken", "down"),
}


def stem(token: str) -> str | None:
    """Suffix-strip one token, or None if no rule applies / result too short.

    Only touches plain ASCII alphabetic tokens -- CJK bigrams and accented
    words from tokenize() pass through untouched rather than risk a wrong
    cut on a script these suffix rules were never designed for.
    """
    if not token.isascii() or not token.isalpha():
        return None
    for suffix, replacement in _SUFFIX_RULES:
        if token.endswith(suffix) and len(token) - len(suffix) + len(replacement) >= _MIN_STEM_LEN:
            stemmed = token[: -len(suffix)] + replacement
            if stemmed != token:
                return stemmed
    return None


def expand_tokens(tokens: list[str]) -> dict[str, Any]:
    """Expand an already-tokenized query. Never called on an empty token list
    by search_atoms() -- that path abstains before expansion is considered,
    so expansion can never manufacture a match out of an untokenizable query.

    Returns:
        {
          "tokens": [new terms only, deduped, excluding originals],
          "added": [{"term", "source_token", "kind"}, ...]  # inspectable trail
        }
    """
    original = set(tokens)
    seen: set[str] = set()
    added: list[dict[str, str]] = []

    for token in tokens:
        stemmed = stem(token)
        if stemmed and stemmed not in original and stemmed not in seen:
            seen.add(stemmed)
            added.append({"term": stemmed, "source_token": token, "kind": "stem"})
        for synonym in SYNONYMS.get(token, ()):
            if synonym not in original and synonym not in seen:
                seen.add(synonym)
                added.append({"term": synonym, "source_token": token, "kind": "synonym"})

    return {"tokens": [entry["term"] for entry in added], "added": added}
