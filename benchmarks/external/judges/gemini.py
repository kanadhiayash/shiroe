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
import os
import re
import ssl
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from benchmarks.external.judges.base import JudgeClient, Verdict
from benchmarks.external.providers.base import Usage

REPO = Path(__file__).resolve().parents[3]

API_BASE = "https://generativelanguage.googleapis.com/v1beta"
REQUEST_TIMEOUT_S = 60
MAX_RETRIES = 3
RETRY_BACKOFF_S = 1.5
# 429 rate-limit and 5xx are transient; 400/401/403 are not and must fail fast
# rather than burning the budget on three doomed retries.
RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})

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


_SSL_CONTEXT: "ssl.SSLContext | None" = None


def _ssl_context() -> "ssl.SSLContext":
    """A verifying TLS context, with an explicit CA bundle if one is needed.

    Some python.org macOS builds ship without a configured trust store, so
    the default context fails CERTIFICATE_VERIFY_FAILED against every host.
    Fall back to certifi's bundle, then the system bundle. Verification is
    NEVER disabled — this connection carries an API key.
    """
    global _SSL_CONTEXT
    if _SSL_CONTEXT is not None:
        return _SSL_CONTEXT
    context = ssl.create_default_context()
    if not context.cert_store_stats().get("x509_ca", 0):
        for candidate in (_certifi_path(), "/etc/ssl/cert.pem"):
            if candidate and Path(candidate).exists():
                context = ssl.create_default_context(cafile=candidate)
                break
    _SSL_CONTEXT = context
    return context


def _certifi_path() -> str | None:
    try:
        import certifi
    except ImportError:
        return None
    return certifi.where()


def _redact(text: str) -> str:
    """Strip anything key-shaped from text bound for an exception or log.

    Defence in depth: the key is sent as a header, never a URL parameter, so
    it should never appear here. This is the backstop for an API error body
    that echoes a request back, or a future refactor that reintroduces a
    query parameter.
    """
    text = re.sub(r"AIza[0-9A-Za-z_\-]{10,}", "[REDACTED-KEY]", text)
    text = re.sub(r"(?i)(key|token|authorization)=[^&\s\"']+", r"\1=[REDACTED]", text)
    return text[:500]


def _first_text(payload: dict[str, Any]) -> str:
    """Pull the model's text out of a generateContent response."""
    for candidate in payload.get("candidates", []):
        for part in candidate.get("content", {}).get("parts", []):
            if isinstance(part.get("text"), str):
                return part["text"]
    return ""


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

# Paid-tier list pricing (USD per million tokens: input, output), verified
# against https://ai.google.dev/gemini-api/docs/pricing on 2026-07-29.
#
# These replace placeholder values that were 20-30x too LOW (0.075/0.30).
# That mattered: cost.estimate_run_cost() drives the --max-cost budget gate,
# so an underestimate would have authorized a run many times more expensive
# than the projection shown to the operator. Re-verify before quoting cost
# publicly, and treat any model missing from this table as unpriced rather
# than cheap — see _rates_for().
PRICING_USD_PER_MTOK: dict[str, tuple[float, float]] = {
    "gemini-3.5-flash": (1.50, 9.00),
    "gemini-3.6-flash": (1.50, 7.50),
    "gemini-2.5-flash": (0.30, 2.50),
    "gemini-2.5-pro": (1.25, 5.00),
}

# Used when a model is absent from the table. Deliberately the most expensive
# known rate, so an unknown model over-estimates cost and trips the budget
# ceiling early rather than silently under-charging the estimate.
_UNKNOWN_MODEL_RATES = (1.50, 9.00)


def _rates_for(model_id: str) -> tuple[float, float]:
    """Price a model, failing expensive rather than cheap when unknown."""
    return PRICING_USD_PER_MTOK.get(model_id, _UNKNOWN_MODEL_RATES)

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
        """POST to the Gemini API, retrying transient failures.

        The key goes in the ``x-goog-api-key`` HEADER, never the URL. urllib
        embeds the URL in HTTPError/URLError strings, so a key in the query
        string would end up in every traceback and log line.
        """
        url = f"{API_BASE}/models/{self.model_id}:generateContent"
        request = urllib.request.Request(
            url,
            data=body,
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": key,
                "User-Agent": "zeref-benchmark-judge/1.0",
            },
            method="POST",
        )
        last_error = ""
        for attempt in range(MAX_RETRIES):
            try:
                with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_S, context=_ssl_context()) as response:
                    return json.loads(response.read())
            except urllib.error.HTTPError as exc:
                # Read the body for the reason, but never echo headers back.
                detail = exc.read(2048).decode("utf-8", "replace") if exc.fp else ""
                last_error = f"HTTP {exc.code}: {_redact(detail)}"
                if exc.code not in RETRYABLE_STATUS:
                    raise RuntimeError(f"Gemini judge call failed — {last_error}") from None
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                last_error = _redact(str(exc))
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_BACKOFF_S * (2 ** attempt))
        raise RuntimeError(
            f"Gemini judge call failed after {MAX_RETRIES} attempts — {last_error}"
        ) from None
