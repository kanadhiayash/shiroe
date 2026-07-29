"""ZRF-61: independent, blind held-out measurement of the criticality classifier.

``tests/test_routing_classifier.py`` is honest about its own limit: its
corpus and the classifier's rules were authored together in one session, so
100% agreement there proves internal consistency, not generalization. This
file exists to answer the question that leaves open: does the classifier
still get the right answer on tasks it never saw, labeled by someone who
had not yet read its rules?

Process (see git history for the two-phase split):
  Phase 1 — ``tests/fixtures/routing_corpus_heldout.jsonl`` was authored and
  committed *before* ``zeref/routing/criticality.py`` or
  ``tests/test_routing_classifier.py`` was read in this session. 68 free-text
  tasks, each hand-labeled LOW/MEDIUM/HIGH/CRITICAL from the rubric in the
  corpus-generation task alone, with ``ambiguous`` and ``debatable`` flags
  recorded honestly where they applied.

  Phase 2 (this file) — written only after reading the classifier. Because
  ``classify()`` scores structured ``TaskSignals``, not free text, each
  corpus task is translated into signals here, by hand, reading the task
  description the same way an on-call engineer filling out a routing request
  would. That translation is a judgment call and the most likely place for
  reviewer disagreement — kept in one place (``SIGNAL_MAP`` below) so it can
  be audited entry by entry. It was written once and not adjusted after
  seeing what it produced.

IMPORTANT — this suite is a measurement instrument, not a quality gate. It
deliberately asserts NO pass/fail threshold on accuracy, CRITICAL recall, or
any of the other rate metrics: asserting a number this same run just
measured would be self-fulfilling and would prove nothing about
generalization. The only assertions here are structural/methodological
(corpus shape, every entry has a signal mapping, under-routing is always
flagged). The actual numbers are printed by
``test_heldout_confusion_matrix_and_metrics_are_published`` — run
``pytest -q -s tests/test_routing_heldout.py`` to see them, and see the
accompanying report for the full confusion matrix, all metrics, and every
individual disagreement with both rationales.
"""

from __future__ import annotations

import json
from pathlib import Path

from zeref.core.reasoning import CRITICALITIES
from zeref.routing.criticality import TaskSignals, classify

REPO = Path(__file__).resolve().parents[1]
CORPUS_PATH = REPO / "tests" / "fixtures" / "routing_corpus_heldout.jsonl"

_LEVELS = CRITICALITIES  # ("LOW", "MEDIUM", "HIGH", "CRITICAL")


def _load_corpus() -> list[dict]:
    entries = []
    with CORPUS_PATH.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            entries.append(json.loads(line))
    return entries


CORPUS = _load_corpus()

# Phase 2 signal extraction: one TaskSignals reading per corpus id, derived
# from the task text only (never adjusted to make a label agree with the
# classifier's output). blast_radius is read consistently as "scope of
# functional/operational impact if this goes wrong", not "who can see the
# diff in version control" — e.g. a typo-only comment fix stays local even
# though it is merged to a shared repo, because nobody's behavior depends on
# a comment.
SIGNAL_MAP: dict[str, dict] = {
    "ht001": dict(reversible=True, blast_radius="local"),
    "ht002": dict(reversible=True, blast_radius="local"),
    "ht003": dict(reversible=True, blast_radius="local"),
    "ht004": dict(reversible=True, blast_radius="team"),
    "ht005": dict(reversible=True, blast_radius="local"),
    "ht006": dict(reversible=True, blast_radius="local"),
    "ht007": dict(reversible=True, blast_radius="local"),
    "ht008": dict(reversible=True, blast_radius="local"),
    "ht009": dict(reversible=True, blast_radius="local"),
    "ht010": dict(reversible=True, blast_radius="team"),
    "ht011": dict(reversible=True, blast_radius="team"),
    "ht012": dict(reversible=True, blast_radius="local"),
    "ht013": dict(reversible=True, blast_radius="local"),
    "ht014": dict(reversible=True, blast_radius="local"),
    "ht015": dict(reversible=True, blast_radius="team"),
    "ht016": dict(reversible=True, blast_radius="team"),
    "ht017": dict(reversible=True, blast_radius="team"),
    "ht018": dict(reversible=True, blast_radius="team", schema_or_migration=True),
    "ht019": dict(reversible=True, blast_radius="org", production_or_credential_access=True),
    "ht020": dict(reversible=True, blast_radius="team"),
    "ht021": dict(reversible=True, blast_radius="team", production_or_credential_access=True),
    "ht022": dict(reversible=True, blast_radius="local"),
    "ht023": dict(reversible=True, blast_radius="team"),
    "ht024": dict(reversible=True, blast_radius="team", schema_or_migration=True),
    "ht025": dict(reversible=True, blast_radius="local"),
    "ht026": dict(reversible=True, blast_radius="team"),
    "ht027": dict(reversible=True, blast_radius="team"),
    "ht028": dict(reversible=True, blast_radius="local"),
    "ht029": dict(reversible=True, blast_radius="local"),
    "ht030": dict(reversible=True, blast_radius="local"),
    "ht031": dict(reversible=True, blast_radius="public"),
    "ht032": dict(reversible=True, blast_radius="public"),
    "ht033": dict(reversible=True, blast_radius="org", privacy_class="confidential"),
    "ht034": dict(reversible=True, blast_radius="public", schema_or_migration=True),
    "ht035": dict(
        reversible=True, blast_radius="org", production_or_credential_access=True, privacy_class="confidential"
    ),
    "ht036": dict(reversible=True, blast_radius="public", production_or_credential_access=True),
    "ht037": dict(reversible=True, blast_radius="public", production_or_credential_access=True),
    "ht038": dict(reversible=False, blast_radius="public", production_or_credential_access=True),
    "ht039": dict(reversible=True, blast_radius="org", production_or_credential_access=True),
    "ht040": dict(reversible=True, blast_radius="org", production_or_credential_access=True),
    "ht041": dict(reversible=True, blast_radius="org", production_or_credential_access=True),
    "ht042": dict(
        reversible=False,
        blast_radius="public",
        schema_or_migration=True,
        production_or_credential_access=True,
        writes_canonical_state=True,
    ),
    "ht043": dict(reversible=True, blast_radius="public", production_or_credential_access=True),
    "ht044": dict(
        reversible=False, blast_radius="public", production_or_credential_access=True, privacy_class="confidential"
    ),
    "ht045": dict(reversible=False, blast_radius="public", schema_or_migration=True),
    "ht046": dict(reversible=True, blast_radius="public", is_public_claim=True, financial_or_legal_impact=True),
    "ht047": dict(reversible=False, blast_radius="team", writes_canonical_state=True),
    "ht048": dict(reversible=True, blast_radius="public", financial_or_legal_impact=True),
    "ht049": dict(
        reversible=False, blast_radius="org", writes_canonical_state=True, privacy_class="confidential"
    ),
    "ht050": dict(
        reversible=True,
        blast_radius="public",
        production_or_credential_access=True,
        financial_or_legal_impact=True,
    ),
    "ht051": dict(reversible=True, blast_radius="team", ambiguous=True),
    "ht052": dict(reversible=True, blast_radius="org", financial_or_legal_impact=True, ambiguous=True),
    "ht053": dict(reversible=False, blast_radius="org", ambiguous=True),
    "ht054": dict(reversible=False, blast_radius="org"),
    "ht055": dict(reversible=True, blast_radius="local"),
    "ht056": dict(
        reversible=False,
        blast_radius="public",
        financial_or_legal_impact=True,
        writes_canonical_state=True,
        privacy_class="restricted",
    ),
    "ht057": dict(
        reversible=False,
        blast_radius="public",
        schema_or_migration=True,
        writes_canonical_state=True,
        production_or_credential_access=True,
    ),
    "ht058": dict(
        reversible=False, blast_radius="public", writes_canonical_state=True, production_or_credential_access=True
    ),
    "ht059": dict(reversible=False, blast_radius="org", financial_or_legal_impact=True, ambiguous=True),
    "ht060": dict(reversible=False, blast_radius="public", financial_or_legal_impact=True, privacy_class="restricted"),
    "ht061": dict(reversible=False, blast_radius="public", production_or_credential_access=True),
    "ht062": dict(reversible=False, blast_radius="public", is_public_claim=True, financial_or_legal_impact=True),
    "ht063": dict(reversible=False, blast_radius="public", is_public_claim=True, financial_or_legal_impact=True),
    "ht064": dict(reversible=False, blast_radius="public", is_public_claim=True),
    "ht065": dict(reversible=False, blast_radius="public", is_public_claim=True, financial_or_legal_impact=True),
    "ht066": dict(reversible=True, blast_radius="public", is_public_claim=True),
    "ht067": dict(
        reversible=True, blast_radius="public", production_or_credential_access=True, writes_canonical_state=True
    ),
    "ht068": dict(
        reversible=True,
        blast_radius="public",
        production_or_credential_access=True,
        financial_or_legal_impact=True,
    ),
}


def _idx(level: str) -> int:
    return _LEVELS.index(level)


def _evaluate(corpus: list[dict]) -> dict:
    confusion = {a: {p: 0 for p in _LEVELS} for a in _LEVELS}
    results = []
    for entry in corpus:
        signals = TaskSignals(**SIGNAL_MAP[entry["id"]])
        result = classify(signals)
        confusion[entry["label"]][result.criticality] += 1
        results.append((entry, signals, result))

    total = len(corpus)
    under = sum(1 for e, s, r in results if _idx(r.criticality) < _idx(e["label"]))
    over = sum(1 for e, s, r in results if _idx(r.criticality) > _idx(e["label"]))
    correct = sum(1 for e, s, r in results if r.criticality == e["label"])
    critical_actual = [e for e in corpus if e["label"] == "CRITICAL"]
    critical_hits = sum(1 for e, s, r in results if e["label"] == "CRITICAL" and r.criticality == "CRITICAL")
    unnecessary_frontier = sum(1 for e, s, r in results if r.criticality == "CRITICAL" and e["label"] != "CRITICAL")
    flagged = sum(1 for _, s, r in results if r.flagged_for_review)

    return {
        "results": results,
        "confusion": confusion,
        "total": total,
        "accuracy": correct / total,
        "critical_recall": (critical_hits / len(critical_actual)) if critical_actual else 1.0,
        "under_routing_rate": under / total,
        "over_routing_rate": over / total,
        "unnecessary_frontier_rate": unnecessary_frontier / total,
        "abstention_rate": flagged / total,
    }


METRICS = _evaluate(CORPUS)


def _print_report() -> None:
    print("\n--- held-out routing corpus confusion matrix (rows=actual, cols=predicted) ---")
    header = "actual\\pred".ljust(12) + "".join(level.ljust(10) for level in _LEVELS)
    print(header)
    for actual in _LEVELS:
        row = METRICS["confusion"][actual]
        print(actual.ljust(12) + "".join(str(row[p]).ljust(10) for p in _LEVELS))
    print(f"total entries:            {METRICS['total']}")
    print(f"overall accuracy:         {METRICS['accuracy']:.3f}")
    print(f"CRITICAL recall:          {METRICS['critical_recall']:.3f}")
    print(f"under-routing rate:       {METRICS['under_routing_rate']:.3f}")
    print(f"over-routing rate:        {METRICS['over_routing_rate']:.3f}")
    print(f"unnecessary-frontier rate:{METRICS['unnecessary_frontier_rate']:.3f}")
    print(f"abstention/flag rate:     {METRICS['abstention_rate']:.3f}")


def test_heldout_corpus_shape_and_coverage() -> None:
    assert len(CORPUS) >= 50, "held-out corpus must have at least 50 blind-labeled tasks"
    labels = {e["label"] for e in CORPUS}
    assert labels == set(_LEVELS), "held-out corpus must span all four criticality levels"
    ids = [e["id"] for e in CORPUS]
    assert len(ids) == len(set(ids)), "held-out corpus ids must be unique"
    assert set(SIGNAL_MAP) == set(ids), "every held-out entry must have a Phase-2 signal mapping"


def test_heldout_confusion_matrix_and_metrics_are_published() -> None:
    """Publish the matrix and all six metrics. No pass/fail threshold — see module docstring."""
    _print_report()
    assert METRICS["total"] == len(CORPUS)
    assert 0.0 <= METRICS["accuracy"] <= 1.0
    assert 0.0 <= METRICS["critical_recall"] <= 1.0
    assert 0.0 <= METRICS["under_routing_rate"] <= 1.0
    assert 0.0 <= METRICS["over_routing_rate"] <= 1.0
    assert 0.0 <= METRICS["unnecessary_frontier_rate"] <= 1.0
    assert 0.0 <= METRICS["abstention_rate"] <= 1.0


def test_heldout_no_entry_routes_below_its_label_without_being_flagged() -> None:
    """Under-routing must never happen silently: it must always carry the review flag.

    This is a check on the classifier's own fail-upward contract, not on
    whether this run's under-routing rate was zero or not — it holds either
    way.
    """
    for entry, signals, result in METRICS["results"]:
        if _idx(result.criticality) < _idx(entry["label"]):
            assert result.flagged_for_review, (
                f"{entry['id']} classified below its label "
                f"({result.criticality} < {entry['label']}) without being flagged for review"
            )
