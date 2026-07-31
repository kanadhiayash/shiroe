"""Grading rules — deterministic, code-enforced.

The invariant enforced here (PR 10 acceptance gate): review robustness
NEVER upgrades source quality. It can lower the effective grade
(when panel dissent or method uniformity contradicts a confidently
sourced claim), it can add caveats, it can cap final confidence — but
`combine(quality=weak, robustness=strong)` is still `weak`.
"""

from __future__ import annotations

from shiroe.evidence.schema import (
    EvidenceGrade,
    EvidenceGradingError,
    EvidenceQualityReport,
    ReviewRobustnessReport,
    SourceRecord,
)


def grade_source_quality(claim: str,
                         sources: list[SourceRecord]) -> EvidenceQualityReport:
    if not sources:
        return EvidenceQualityReport(
            claim=claim, grade=EvidenceGrade.unknown,
            reasons=["no sources"],
        )
    reasons: list[str] = []
    factors: dict[str, float] = {}

    direct = [s for s in sources if s.direct]
    factors["directness"] = len(direct) / len(sources)
    factors["authority"] = sum(s.authority for s in sources) / len(sources)
    factors["corroboration"] = min(1.0,
                                    sum(len(s.corroborated_by) for s in sources) / (2 * len(sources)))
    factors["reproducibility"] = sum(1 for s in sources if s.reproducible) / len(sources)
    factors["provenance"] = sum(
        1 for s in sources if s.kind in ("primary", "secondary")
    ) / len(sources)

    contradicting = [s for s in sources if s.contradicts]
    factors["contradiction_penalty"] = len(contradicting) / len(sources)

    # Aggregate — weighted average with a hard contradiction override.
    aggregate = (
        0.30 * factors["directness"]
        + 0.25 * factors["authority"]
        + 0.20 * factors["corroboration"]
        + 0.15 * factors["reproducibility"]
        + 0.10 * factors["provenance"]
    )

    if factors["contradiction_penalty"] >= 0.5:
        grade = EvidenceGrade.conflicting
        reasons.append("majority of sources contradict at least one other source")
    elif aggregate >= 0.75 and factors["directness"] >= 0.5:
        grade = EvidenceGrade.strong
        reasons.append(f"aggregate score {aggregate:.2f}, direct sources present")
    elif aggregate >= 0.5:
        grade = EvidenceGrade.moderate
        reasons.append(f"aggregate score {aggregate:.2f}")
    else:
        grade = EvidenceGrade.weak
        reasons.append(f"aggregate score {aggregate:.2f}")

    return EvidenceQualityReport(
        claim=claim, grade=grade, reasons=reasons,
        source_ids=[s.id for s in sources], factors=factors,
    )


def grade_review_robustness(claim: str,
                             *,
                             reviewers: list[str],
                             independent_agreement: float,
                             dissent_ratio: float,
                             counterarguments_considered: int,
                             method_diversity: float,
                             decision_stability: float) -> ReviewRobustnessReport:
    for name, val in (
        ("independent_agreement", independent_agreement),
        ("dissent_ratio", dissent_ratio),
        ("method_diversity", method_diversity),
        ("decision_stability", decision_stability),
    ):
        if not (0.0 <= val <= 1.0):
            raise EvidenceGradingError(
                f"{name} must be in [0, 1]; got {val}"
            )
    return ReviewRobustnessReport(
        claim=claim,
        method_diversity=method_diversity,
        independent_agreement=independent_agreement,
        dissent_ratio=dissent_ratio,
        counterarguments_considered=counterarguments_considered,
        decision_stability=decision_stability,
        reviewers=list(reviewers),
    )


# Grade ordering used by combine() — later positions are weaker.
_ORDER = {
    EvidenceGrade.strong: 4,
    EvidenceGrade.moderate: 3,
    EvidenceGrade.weak: 2,
    EvidenceGrade.unknown: 1,
    EvidenceGrade.conflicting: 0,
}


def combine(quality: EvidenceQualityReport,
            robustness: ReviewRobustnessReport | None) -> EvidenceQualityReport:
    """Fold review robustness into an evidence quality report.

    Rules:
    - Robustness NEVER upgrades a weaker quality grade.
    - High dissent + high method diversity + low decision stability may
      DOWNGRADE (weak → conflicting).
    - Low independent agreement lowers `strong` to `moderate`.

    Returns a new EvidenceQualityReport (input is not mutated).
    """
    grade = quality.grade
    reasons = list(quality.reasons)
    factors = dict(quality.factors)

    if robustness is not None:
        factors["review.independent_agreement"] = robustness.independent_agreement
        factors["review.dissent_ratio"] = robustness.dissent_ratio
        factors["review.method_diversity"] = robustness.method_diversity
        factors["review.decision_stability"] = robustness.decision_stability

        # Downgrade — never upgrade.
        if (robustness.dissent_ratio >= 0.5
                and robustness.decision_stability <= 0.5):
            if _ORDER[grade] > _ORDER[EvidenceGrade.weak]:
                grade = EvidenceGrade.weak
                reasons.append(
                    "downgraded: high dissent + low decision stability"
                )
            elif grade is EvidenceGrade.weak:
                grade = EvidenceGrade.conflicting
                reasons.append(
                    "downgraded to conflicting: dissent + instability + weak source"
                )
        elif grade is EvidenceGrade.strong \
                and robustness.independent_agreement < 0.5:
            grade = EvidenceGrade.moderate
            reasons.append(
                "downgraded: independent agreement below 0.5"
            )

    return EvidenceQualityReport(
        claim=quality.claim, grade=grade, reasons=reasons,
        source_ids=list(quality.source_ids), factors=factors,
    )
