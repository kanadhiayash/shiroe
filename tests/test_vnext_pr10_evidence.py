"""vNext PR 10 gate tests — evidence engine v2."""

from __future__ import annotations

import pytest

from shiroe.evidence import (
    ContradictionError,
    EvidenceGrade,
    EvidenceGradingError,
    SourceRecord,
    combine,
    detect_contradictions,
    grade_review_robustness,
    grade_source_quality,
    record_reproduction,
)


def _weak_source(sid: str = "s1") -> SourceRecord:
    return SourceRecord(
        id=sid, kind="hearsay", ref="rumour",
        direct=False, authority=0.2, reproducible=False,
    )


def _strong_source(sid: str = "s1") -> SourceRecord:
    return SourceRecord(
        id=sid, kind="primary", ref="doi:10/example",
        direct=True, authority=0.95, reproducible=True,
        corroborated_by=["s2", "s3"],
    )


def test_no_sources_is_unknown() -> None:
    q = grade_source_quality("claim", [])
    assert q.grade is EvidenceGrade.unknown


def test_strong_sources_grade_strong() -> None:
    q = grade_source_quality("claim", [
        _strong_source("s1"),
        SourceRecord(id="s2", kind="primary", ref="ref2",
                     direct=True, authority=0.9, reproducible=True,
                     corroborated_by=["s1"]),
    ])
    assert q.grade is EvidenceGrade.strong


def test_weak_sources_grade_weak() -> None:
    q = grade_source_quality("claim", [_weak_source()])
    assert q.grade is EvidenceGrade.weak


def test_contradiction_majority_flags_conflicting() -> None:
    q = grade_source_quality("claim", [
        SourceRecord(id="s1", kind="primary", ref="a",
                     direct=True, authority=0.9, contradicts=["s2"]),
        SourceRecord(id="s2", kind="primary", ref="b",
                     direct=True, authority=0.9, contradicts=["s1"]),
    ])
    assert q.grade is EvidenceGrade.conflicting


def test_review_robustness_input_validation() -> None:
    with pytest.raises(EvidenceGradingError):
        grade_review_robustness("c", reviewers=["r1"],
                                independent_agreement=1.5,
                                dissent_ratio=0.0,
                                counterarguments_considered=0,
                                method_diversity=0.5,
                                decision_stability=0.5)


# ---------------------------------------------------------------------------
# The PR 10 acceptance gate — robustness never upgrades quality.
# ---------------------------------------------------------------------------

def test_review_never_upgrades_weak_quality() -> None:
    q = grade_source_quality("claim", [_weak_source()])
    assert q.grade is EvidenceGrade.weak

    strong_review = grade_review_robustness(
        "claim", reviewers=["r1", "r2", "r3"],
        independent_agreement=1.0, dissent_ratio=0.0,
        counterarguments_considered=5,
        method_diversity=1.0, decision_stability=1.0,
    )
    combined = combine(q, strong_review)
    # Council agreement CANNOT promote weak source evidence.
    assert combined.grade is EvidenceGrade.weak


def test_dissent_plus_instability_downgrades() -> None:
    q = grade_source_quality("claim", [
        _strong_source("s1"),
        SourceRecord(id="s2", kind="primary", ref="r",
                     direct=True, authority=0.9, reproducible=True,
                     corroborated_by=["s1"]),
    ])
    assert q.grade is EvidenceGrade.strong

    dissent_review = grade_review_robustness(
        "claim", reviewers=["r1", "r2", "r3"],
        independent_agreement=0.3, dissent_ratio=0.7,
        counterarguments_considered=4,
        method_diversity=0.8, decision_stability=0.4,
    )
    combined = combine(q, dissent_review)
    assert combined.grade in (EvidenceGrade.weak, EvidenceGrade.moderate,
                              EvidenceGrade.conflicting)


def test_low_independent_agreement_downgrades_strong_to_moderate() -> None:
    q = grade_source_quality("claim", [
        _strong_source("s1"),
        SourceRecord(id="s2", kind="primary", ref="r",
                     direct=True, authority=0.9, reproducible=True,
                     corroborated_by=["s1"]),
    ])
    assert q.grade is EvidenceGrade.strong

    low_agreement = grade_review_robustness(
        "claim", reviewers=["r1", "r2"],
        independent_agreement=0.4, dissent_ratio=0.2,
        counterarguments_considered=2,
        method_diversity=0.5, decision_stability=0.8,
    )
    combined = combine(q, low_agreement)
    assert combined.grade is EvidenceGrade.moderate


# ---------------------------------------------------------------------------
# Contradictions
# ---------------------------------------------------------------------------

def test_detect_contradictions_pairs_deduped() -> None:
    sources = [
        SourceRecord(id="a", kind="primary", ref="1",
                     direct=True, authority=0.9, contradicts=["b"]),
        SourceRecord(id="b", kind="primary", ref="2",
                     direct=True, authority=0.9, contradicts=["a"]),
    ]
    con = detect_contradictions("claim", sources)
    assert len(con) == 1
    pair = (con[0].side_a, con[0].side_b)
    assert pair == ("a", "b")


def test_reproducibility_record() -> None:
    rep = record_reproduction(
        claim="claim", source_id="s1",
        reproduced_by="tester", ok=True, notes="ran fine",
    )
    assert rep.ok
    assert rep.claim == "claim"
    assert rep.id.startswith("rep_")
