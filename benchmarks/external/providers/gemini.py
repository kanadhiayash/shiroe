"""
privacy-audit: allow-file "Provider names the API-key env var and pricing schema as spec; no credential values, no user data."

Gemini generation provider.

Lets a scored run be driven by a Gemini key alone, with no Anthropic account.
Shares all transport, key handling and pricing with the judge via
``benchmarks.external.gemini_api``, so the security-critical parts exist once.

``dry_run=True`` is the default and returns a priced empty completion without
touching the network, matching ``AnthropicProvider``. A live call needs
``dry_run=False`` AND a key on disk, so no test and no proxy run can bill.

JUDGE INDEPENDENCE — read before quoting any number produced this way. When
generation and judging both run on Gemini, the judge is scoring its own
model family's output, and LLM judges are known to prefer it. That does NOT
invalidate the comparison this harness makes, because all three arms
(zeref, full_context, bm25) share one generator and one judge, so the bias
applies equally to all three and the RELATIVE ranking still holds. It DOES
invalidate an absolute leaderboard claim ("we scored X on LoCoMo"). Use a
different model for the generator than for the judge, and keep the caveat
attached to the result — ``runner`` records it in provenance as
``judge_independence``.
"""

from __future__ import annotations

import json
import time

from benchmarks.external import gemini_api
from benchmarks.external.providers.base import Completion, Provider, Usage

# Cheapest entry in the verified pricing table, and deliberately NOT the
# judge's default model — see the judge-independence note above.
DEFAULT_MODEL_ID = "gemini-2.5-flash"


class GeminiProvider(Provider):
    name = "gemini"

    def __init__(self, model_id: str = DEFAULT_MODEL_ID, dry_run: bool = True) -> None:
        self.model_id = model_id
        self.dry_run = dry_run
        # Boolean only — the raw key is read on demand and never stored.
        self._has_key = gemini_api.read_api_key() is not None

    def has_key(self) -> bool:
        """Whether a key was found. Never exposes the key itself."""
        return self._has_key

    def estimate(self, prompt: str, expected_output_tokens: int = 256) -> Usage:
        input_tokens = max(1, len(prompt) // gemini_api.CHARS_PER_TOKEN)
        in_rate, out_rate = gemini_api.rates_for(self.model_id)
        cost = (input_tokens * in_rate + expected_output_tokens * out_rate) / 1_000_000
        return Usage(
            input_tokens=input_tokens,
            output_tokens=expected_output_tokens,
            cost_usd=cost,
            estimated=True,
        )

    def complete(self, prompt: str, max_tokens: int = 512) -> Completion:
        """Run one completion.

        ``dry_run=True`` (the default) returns an empty completion priced by
        ``estimate`` — no network, no bill. A live call needs an explicit
        ``dry_run=False`` and a key.
        """
        if self.dry_run:
            return Completion(text="", usage=self.estimate(prompt, max_tokens))

        key = gemini_api.read_api_key()
        if not key:
            raise RuntimeError(
                "no GEMINI_API_KEY found in the environment or .env.local. "
                "(The key value is never logged or echoed by this provider.)"
            )

        body = json.dumps({
            "contents": [{"parts": [{"text": prompt}]}],
            # Deterministic generation: a generator that varies run to run
            # makes two arms incomparable, which is the point of the exercise.
            "generationConfig": {
                "temperature": 0.0,
                "maxOutputTokens": max_tokens,
            },
        }).encode("utf-8")

        started = time.monotonic()
        payload = gemini_api.post(self.model_id, key, body, what="provider")
        _ = (time.monotonic() - started)  # latency is recorded by the judge path

        text = gemini_api.first_text(payload)
        meta = payload.get("usageMetadata", {})
        input_tokens = int(meta.get("promptTokenCount", 0))
        output_tokens = int(meta.get("candidatesTokenCount", 0))
        in_rate, out_rate = gemini_api.rates_for(self.model_id)
        cost = (input_tokens * in_rate + output_tokens * out_rate) / 1_000_000
        return Completion(
            text=text,
            usage=Usage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=cost,
                # Token counts are reported by the API; the dollar figure is
                # still derived from the local pricing table.
                estimated=False,
            ),
        )
