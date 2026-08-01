"""
privacy-audit: allow-file "Judge client stub names the API-key env var and pricing schema as spec; no credential values, no user data."

Gemini judge client with live scoring.

Reads GEMINI_API_KEY from the environment or a gitignored .env.local at the
repo root (see PRIVACY.md / REDACT.md). The raw key value is NEVER stored on
the instance, printed, logged, or included in an error message — only
whether one was found (`has_key()`), which is all any caller needs to reason
about readiness. The key is sent as an ``x-goog-api-key`` header and never
as a URL parameter, because urllib puts the request URL into every
HTTPError/URLError string and that is where a key would otherwise leak.

Live calls are OPT-IN PER INSTANCE: ``GeminiJudgeClient(live=True)``. The
default is estimate-only and ``judge()`` raises, so no test and no dry run
can reach the network or bill the account, and no environment variable can
turn a dry run into a billed one. Tests use ``DeterministicFakeJudge``.
"""

from __future__ import annotations

import json
import re
import time
from typing import Any

from benchmarks.external import gemini_api
from benchmarks.external.judges.base import JudgeClient, Verdict
from benchmarks.external.providers.base import Usage

# Transport, key handling, redaction and pricing are shared with the
# generation provider — see benchmarks/external/gemini_api.py. Re-exported
# here so existing callers and tests keep working.
MAX_RETRIES = gemini_api.MAX_RETRIES
RETRYABLE_STATUS = gemini_api.RETRYABLE_STATUS
CHARS_PER_TOKEN = gemini_api.CHARS_PER_TOKEN
PRICING_USD_PER_MTOK = gemini_api.PRICING_USD_PER_MTOK
_read_api_key = gemini_api.read_api_key
_redact = gemini_api.redact
_first_text = gemini_api.first_text
_rates_for = gemini_api.rates_for

# Asks for a judgement, not a rewrite: the judge decides whether the
# prediction conveys a gold answer, and is told explicitly that wording may
# differ. The abstention clause matters for ConvoMem, where the correct
# answer is often "this was never mentioned" phrased as a full sentence.
JUDGE_PROMPT = """You are grading one answer against reference answers.

Question:
{question}

Reference answer(s):
{gold}

Candidate answer:
{prediction}

Decide whether the candidate conveys the same information as ANY reference
answer. Wording, formatting and extra detail do not matter; the factual
content does. If the reference indicates the information was never provided
or is unanswerable, then a candidate that declines or says it does not know
is CORRECT.

Respond with JSON only:
{{"correct": true or false, "score": 0.0 to 1.0, "rationale": "one short sentence"}}"""


def _parse_verdict(text: str) -> tuple[bool, float, str]:
    """Parse the judge's JSON reply.

    An unparseable reply is scored INCORRECT rather than skipped. Treating a
    malformed verdict as a pass would inflate whichever arm happened to
    trigger it; treating it as a skip would silently shrink the denominator.
    Either way the run should show the damage, so the rationale records it.
    """
    raw = text.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            return False, 0.0, f"unparseable judge reply: {raw[:120]!r}"
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            return False, 0.0, f"unparseable judge reply: {raw[:120]!r}"
    if not isinstance(data, dict):
        return False, 0.0, f"unexpected judge reply shape: {raw[:120]!r}"
    correct = bool(data.get("correct", False))
    try:
        score = float(data.get("score", 1.0 if correct else 0.0))
    except (TypeError, ValueError):
        score = 1.0 if correct else 0.0
    score = min(1.0, max(0.0, score))
    rationale = str(data.get("rationale", ""))[:300]
    return correct, score, rationale


def _usage_from_response(payload: dict[str, Any], model_id: str) -> Usage:
    """Real token counts from the API, priced at the local table.

    ``estimated=False`` here because the token counts are reported by the
    API. The dollar figure is still derived from PRICING_USD_PER_MTOK, which
    is a local constant — verify it against Google's published pricing before
    quoting any cost publicly.
    """
    meta = payload.get("usageMetadata", {})
    input_tokens = int(meta.get("promptTokenCount", 0))
    output_tokens = int(meta.get("candidatesTokenCount", 0))
    in_rate, out_rate = _rates_for(model_id)
    cost = (input_tokens * in_rate + output_tokens * out_rate) / 1_000_000
    return Usage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost,
        estimated=False,
    )

DEFAULT_MODEL_ID = "gemini-3.5-flash"

# Judge verdicts are short (a verdict plus a brief rationale) regardless of
# input size — used as the fixed expected-output-token estimate below.
EXPECTED_OUTPUT_TOKENS = 32


class GeminiJudgeClient(JudgeClient):
    name = "gemini"

    def __init__(self, model_id: str = DEFAULT_MODEL_ID, *, live: bool = False) -> None:
        self.model_id = model_id
        # Boolean only — the raw key is read once, above, and discarded.
        self._has_key = _read_api_key() is not None
        # Live calls are opt-in per instance, not per environment variable, so
        # a stray env var can never turn a dry run into a billed one. The CLI
        # sets this only under --live --confirm.
        self._live = live

    def has_key(self) -> bool:
        """Whether a judge key was found. Never exposes the key itself."""
        return self._has_key

    def estimate(self, question: str, gold_answers: tuple[str, ...], prediction: str) -> Usage:
        prompt_len = len(question) + sum(len(a) for a in gold_answers) + len(prediction)
        input_tokens = max(1, prompt_len // CHARS_PER_TOKEN)
        in_rate, out_rate = _rates_for(self.model_id)
        cost = (input_tokens * in_rate + EXPECTED_OUTPUT_TOKENS * out_rate) / 1_000_000
        return Usage(
            input_tokens=input_tokens,
            output_tokens=EXPECTED_OUTPUT_TOKENS,
            cost_usd=cost,
            estimated=True,
        )

    def judge(self, question: str, gold_answers: tuple[str, ...], prediction: str) -> Verdict:
        """Score one prediction with a live Gemini call.

        Requires ``live=True`` at construction AND a key on disk. Tests must
        never reach this method — they use ``DeterministicFakeJudge``.

        Every failure path here re-raises WITHOUT the request URL, because
        the key travels as a URL query parameter and urllib puts the full URL
        in the exception string. That is the one place a key would otherwise
        leak into a traceback, a CI log, or a results file.
        """
        if not self._live:
            raise RuntimeError(
                "live Gemini judging is disabled on this client. Construct "
                "GeminiJudgeClient(live=True) to enable it; the default stays "
                "estimate-only so no test or dry run can call the API."
            )
        key = _read_api_key()
        if not key:
            raise RuntimeError(
                "no GEMINI_API_KEY found in the environment or .env.local. "
                "(The key value is never logged or echoed by this client.)"
            )

        prompt = JUDGE_PROMPT.format(
            question=question,
            gold="\n".join(f"- {answer}" for answer in gold_answers),
            prediction=prediction,
        )
        body = json.dumps({
            "contents": [{"parts": [{"text": prompt}]}],
            # Deterministic scoring: a judge that varies run to run makes two
            # arms incomparable, which is the whole point of the exercise.
            "generationConfig": {
                "temperature": 0.0,
                "maxOutputTokens": 256,
                "responseMimeType": "application/json",
            },
        }).encode("utf-8")

        started = time.monotonic()
        payload = self._post(key, body)
        latency_ms = (time.monotonic() - started) * 1000.0

        text = _first_text(payload)
        correct, score, rationale = _parse_verdict(text)
        usage = _usage_from_response(payload, self.model_id)
        return Verdict(
            correct=correct,
            score=score,
            rationale=rationale,
            usage=usage,
            latency_ms=latency_ms,
        )

    def _post(self, key: str, body: bytes) -> dict:
        """Delegate to the shared Gemini transport (see gemini_api.post)."""
        return gemini_api.post(self.model_id, key, body, what="judge")
