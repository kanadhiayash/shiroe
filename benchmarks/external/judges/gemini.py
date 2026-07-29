"""
privacy-audit: allow-file "Judge client stub names the API-key env var and pricing schema as spec; no credential values, no user data."

Gemini judge client (real, Wave 4 build).

Reads GEMINI_API_KEY from the environment or a gitignored .env.local at the
repo root (see PRIVACY.md / REDACT.md). The raw key value is NEVER stored on
the instance, printed, logged, or included in an error message — only
whether one was found (`has_key()`), which is all any caller needs to reason
about readiness. Live judge calls are disabled in this build; a later
authorized session enables them. Until then this client only supports
estimate(), matching `providers.anthropic.AnthropicProvider`'s Phase A
posture exactly.
"""

from __future__ import annotations

import os
from pathlib import Path

from benchmarks.external.judges.base import JudgeClient, Verdict
from benchmarks.external.providers.base import Usage

REPO = Path(__file__).resolve().parents[3]

DEFAULT_MODEL_ID = "gemini-2.5-flash"

# PLACEHOLDER pricing (USD per million tokens) for dry-run cost ESTIMATES
# only. Must be re-verified against the official Gemini pricing page before
# any live run publishes cost numbers.
PRICING_USD_PER_MTOK: dict[str, tuple[float, float]] = {
    "gemini-2.5-flash": (0.075, 0.30),
    "gemini-2.5-pro": (1.25, 5.00),
}

# Rough chars-per-token heuristic for dry-run estimates (no tokenizer, no API).
CHARS_PER_TOKEN = 4

# Judge verdicts are short (a verdict plus a brief rationale) regardless of
# input size — used as the fixed expected-output-token estimate below.
EXPECTED_OUTPUT_TOKENS = 32


def _read_api_key() -> str | None:
    """Env var wins; falls back to a gitignored .env.local at the repo root.

    Returns the raw key or None. Callers must not retain the return value —
    `GeminiJudgeClient` only stores a boolean derived from it.
    """
    key = os.environ.get("GEMINI_API_KEY")
    if key:
        return key
    env_local = REPO / ".env.local"
    if not env_local.exists():
        return None
    try:
        for line in env_local.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, _, value = line.partition("=")
            if name.strip() == "GEMINI_API_KEY":
                value = value.strip().strip('"').strip("'")
                return value or None
    except OSError:
        return None
    return None


class GeminiJudgeClient(JudgeClient):
    name = "gemini"

    def __init__(self, model_id: str = DEFAULT_MODEL_ID) -> None:
        self.model_id = model_id
        # Boolean only — the raw key is read once, above, and discarded.
        self._has_key = _read_api_key() is not None

    def has_key(self) -> bool:
        """Whether a judge key was found. Never exposes the key itself."""
        return self._has_key

    def estimate(self, question: str, gold_answers: tuple[str, ...], prediction: str) -> Usage:
        prompt_len = len(question) + sum(len(a) for a in gold_answers) + len(prediction)
        input_tokens = max(1, prompt_len // CHARS_PER_TOKEN)
        in_rate, out_rate = PRICING_USD_PER_MTOK.get(self.model_id, (0.075, 0.30))
        cost = (input_tokens * in_rate + EXPECTED_OUTPUT_TOKENS * out_rate) / 1_000_000
        return Usage(
            input_tokens=input_tokens,
            output_tokens=EXPECTED_OUTPUT_TOKENS,
            cost_usd=cost,
            estimated=True,
        )

    def judge(self, question: str, gold_answers: tuple[str, ...], prediction: str) -> Verdict:
        raise RuntimeError(
            "Live Gemini judge calls are disabled in this build (external "
            "benchmark harness construction). A later authorized session "
            "enables live scoring; until then this client only supports "
            "estimate()."
        )
