"""LLM-as-judge adapter interface with mandatory cost recording.

Mirrors `benchmarks.external.providers.base.Provider`: implementations MUST
record usage for every call (including a fake/estimate call), and live
implementations must gate real network calls behind an explicit opt-in that
is never exercised from tests.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from benchmarks.external.providers.base import Usage


@dataclass(frozen=True)
class Verdict:
    """One judge call's verdict for a (question, gold answers, prediction) triple."""

    correct: bool
    score: float  # 0.0-1.0
    rationale: str
    usage: Usage
    # Judge-reported latency, not runner-measured wall-clock — keeps
    # provenance reproducible for fake/estimate judges (always 0.0) while
    # leaving room for a real client to report its actual call latency.
    latency_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "correct": self.correct,
            "score": self.score,
            "rationale": self.rationale,
            "usage": self.usage.to_dict(),
            "latency_ms": self.latency_ms,
        }


class JudgeClient(ABC):
    """Scores a generated prediction against gold answers.

    Implementations MUST record usage for every call so results JSON always
    carries a token/cost record. Live inference must be an explicit opt-in
    that raises unless truly enabled — see `judges.gemini.GeminiJudgeClient`.
    """

    name: str
    model_id: str

    @abstractmethod
    def estimate(self, question: str, gold_answers: tuple[str, ...], prediction: str) -> Usage:
        """Estimate token count/cost for one judge call WITHOUT calling any API."""

    @abstractmethod
    def judge(self, question: str, gold_answers: tuple[str, ...], prediction: str) -> Verdict:
        """Score one prediction. Real clients: live calls only when explicitly enabled."""
