"""LLM-as-judge adapters for scoring generated predictions against gold answers."""

from __future__ import annotations

from benchmarks.external.judges.base import JudgeClient, Verdict

__all__ = ["JudgeClient", "Verdict"]
