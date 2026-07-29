"""Deterministic fake judge — zero network, used for ALL harness tests.

Never swap this out inside a test. `judge()` decides "correct" the same way
`harness.exact_match` does (normalized string equality against any gold
answer) so its verdicts are predictable and reproducible byte-for-byte
(besides the run's `timestamp`), including a fixed synthetic per-call cost
so cost-accounting math has something nonzero to exercise offline.
"""

from __future__ import annotations

from benchmarks.external.harness import normalize_answer
from benchmarks.external.judges.base import JudgeClient, Verdict
from benchmarks.external.providers.base import Usage

# ponytail: round, fixed numbers so a failing test's running-cost total is
# easy to eyeball by hand. Not a pricing claim of any kind — pure fixture.
_INPUT_TOKENS = 50
_OUTPUT_TOKENS = 10
_COST_PER_CALL_USD = 0.0002


class DeterministicFakeJudge(JudgeClient):
    name = "fake"
    model_id = "deterministic-fake-judge-v1"

    def estimate(self, question: str, gold_answers: tuple[str, ...], prediction: str) -> Usage:
        return Usage(
            input_tokens=_INPUT_TOKENS,
            output_tokens=_OUTPUT_TOKENS,
            cost_usd=_COST_PER_CALL_USD,
            estimated=True,
        )

    def judge(self, question: str, gold_answers: tuple[str, ...], prediction: str) -> Verdict:
        prediction_norm = normalize_answer(prediction)
        correct = any(prediction_norm == normalize_answer(answer) for answer in gold_answers)
        return Verdict(
            correct=correct,
            score=1.0 if correct else 0.0,
            rationale="deterministic fake judge: exact normalized-string match against gold answers",
            usage=self.estimate(question, gold_answers, prediction),
            latency_ms=0.0,
        )
