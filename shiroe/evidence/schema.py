"""Evidence types."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class EvidenceGrade(str, Enum):
    strong = "strong"
    moderate = "moderate"
    weak = "weak"
    unknown = "unknown"
    conflicting = "conflicting"


class EvidenceGradingError(ValueError):
    pass


@dataclass
class SourceRecord:
    id: str
    kind: str                  # "primary", "secondary", "hearsay", "model_output"
    ref: str                   # URL, DOI, file path, JSONL row ref
    direct: bool = False       # does the source directly support the claim?
    authority: float = 0.5     # 0..1
    recency_days: int | None = None
    reproducible: bool = False
    corroborated_by: list[str] = field(default_factory=list)
    contradicts: list[str] = field(default_factory=list)


@dataclass
class EvidenceQualityReport:
    claim: str
    grade: EvidenceGrade
    reasons: list[str] = field(default_factory=list)
    source_ids: list[str] = field(default_factory=list)
    factors: dict[str, float] = field(default_factory=dict)


@dataclass
class ReviewRobustnessReport:
    claim: str
    method_diversity: float          # 0..1
    independent_agreement: float     # 0..1
    dissent_ratio: float             # 0..1
    counterarguments_considered: int
    decision_stability: float        # 0..1
    reviewers: list[str] = field(default_factory=list)


@dataclass
class ContradictionRecord:
    id: str
    side_a: str
    side_b: str
    detected_at: str
    reason: str
    grades: dict[str, str]           # per side_a / side_b


class SourceQualityFactor(str, Enum):
    provenance = "provenance"
    directness = "directness"
    recency = "recency"
    authority = "authority"
    corroboration = "corroboration"
    reproducibility = "reproducibility"
    contradictions = "contradictions"
