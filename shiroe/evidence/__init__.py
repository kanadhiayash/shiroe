"""Evidence engine v2 (vNext PR 10, master plan §11).

Two independent results per claim:

- **Evidence quality** — properties of the sources: provenance,
  directness, recency, authority, corroboration, reproducibility,
  contradictions.
- **Review robustness** — properties of the deliberation: method
  diversity, independent agreement, dissent, alternative framings,
  counterarguments, risk analysis, decision stability.

Council agreement never automatically upgrades weak source evidence to a
strong grade. That invariant lives here (grading.py) and is the PR-10
acceptance gate.
"""

from shiroe.evidence.schema import (
    ContradictionRecord,
    EvidenceGrade,
    EvidenceGradingError,
    EvidenceQualityReport,
    ReviewRobustnessReport,
    SourceRecord,
)
from shiroe.evidence.grading import (
    grade_source_quality,
    grade_review_robustness,
    combine,
)
from shiroe.evidence.contradictions import (
    detect_contradictions,
    ContradictionError,
)
from shiroe.evidence.reproducibility import (
    ReproducibilityRecord,
    record_reproduction,
)

__all__ = [
    "ContradictionRecord", "EvidenceGrade", "EvidenceGradingError",
    "EvidenceQualityReport", "ReviewRobustnessReport", "SourceRecord",
    "grade_source_quality", "grade_review_robustness", "combine",
    "detect_contradictions", "ContradictionError",
    "ReproducibilityRecord", "record_reproduction",
]
