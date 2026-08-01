"""
privacy-audit: allow-file "Tests reference env-var names and fake payloads only; no real credentials, no user data."

Mocked-transport tests for the live Gemini paths: GeminiProvider.complete
(dry_run=False) and GeminiJudgeClient.judge(live=True). Both share the same
transport (benchmarks.external.gemini_api.post), so both are covered here.

Only the no-key refusal paths had coverage before this file (see
test_external_harness_wave4.py). The live HTTP path — success parsing, real
usage-derived cost, 429 retry, fail-fast on a non-retryable error, and (for
the judge) verdict parsing including the fenced/malformed cases — had never
been exercised. Every test here stubs urllib.request.urlopen at the shared
gemini_api module boundary, matching tests/test_ollama_provider.py's shape,
so nothing here can make a real network call or spend a real key.
"""

from __future__ import annotations

import io
import json
import urllib.error

import pytest

from benchmarks.external import gemini_api
from benchmarks.external.judges.gemini import DEFAULT_MODEL_ID as JUDGE_MODEL_ID
from benchmarks.external.judges.gemini import GeminiJudgeClient
from benchmarks.external.providers.gemini import DEFAULT_MODEL_ID as PROVIDER_MODEL_ID
from benchmarks.external.providers.gemini import GeminiProvider


class _FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False


def _http_error(code: int, body: bytes = b"{}") -> urllib.error.HTTPError:
    return urllib.error.HTTPError(
        url="https://generativelanguage.googleapis.com/v1beta/models/x:generateContent",
        code=code, msg="error", hdrs=None, fp=io.BytesIO(body),
    )


def _sequenced_urlopen(monkeypatch, responses: list, calls: dict) -> None:
    """Each call pops the next scripted response/exception in order."""
    def fake_urlopen(request, timeout=None, context=None):
        calls["n"] = calls.get("n", 0) + 1
        calls.setdefault("requests", []).append(request)
        item = responses[calls["n"] - 1]
        if isinstance(item, BaseException):
            raise item
        return _FakeResponse(json.dumps(item).encode())

    monkeypatch.setattr(
        "benchmarks.external.gemini_api.urllib.request.urlopen", fake_urlopen
    )
    monkeypatch.setattr("benchmarks.external.gemini_api.time.sleep", lambda *_: None)


def _gen_payload(text: str, prompt_tokens: int, out_tokens: int) -> dict:
    return {
        "candidates": [{"content": {"parts": [{"text": text}]}}],
        "usageMetadata": {"promptTokenCount": prompt_tokens, "candidatesTokenCount": out_tokens},
    }


# ---------------------------------------------------------------------------
# GeminiProvider.complete(dry_run=False)
# ---------------------------------------------------------------------------

def _live_provider(monkeypatch) -> GeminiProvider:
    monkeypatch.setenv("GEMINI_API_KEY", "AIzaSentinelTestKey1234567890")
    return GeminiProvider(dry_run=False)


def test_provider_successful_call_parses_text_and_real_usage(monkeypatch) -> None:
    provider = _live_provider(monkeypatch)
    calls: dict = {}
    _sequenced_urlopen(monkeypatch, [_gen_payload("Paris.", 41, 3)], calls)

    completion = provider.complete("capital of France?")

    assert completion.text == "Paris."
    assert completion.usage.input_tokens == 41
    assert completion.usage.output_tokens == 3
    assert completion.usage.estimated is False
    in_rate, out_rate = gemini_api.rates_for(PROVIDER_MODEL_ID)
    expected_cost = (41 * in_rate + 3 * out_rate) / 1_000_000
    assert completion.usage.cost_usd == pytest.approx(expected_cost)
    assert calls["n"] == 1


def test_provider_retries_on_429_then_succeeds(monkeypatch) -> None:
    provider = _live_provider(monkeypatch)
    calls: dict = {}
    _sequenced_urlopen(monkeypatch, [
        _http_error(429, b'{"error": "rate limited"}'),
        _gen_payload("ok", 5, 1),
    ], calls)

    completion = provider.complete("q")

    assert completion.text == "ok"
    assert calls["n"] == 2


def test_provider_non_retryable_error_fails_fast(monkeypatch) -> None:
    provider = _live_provider(monkeypatch)
    calls: dict = {}
    _sequenced_urlopen(monkeypatch, [
        _http_error(401, b'{"error": "bad key"}'),
        _gen_payload("should never be reached", 1, 1),
    ], calls)

    with pytest.raises(RuntimeError, match="HTTP 401"):
        provider.complete("q")

    assert calls["n"] == 1


# ---------------------------------------------------------------------------
# GeminiJudgeClient.judge(live=True)
# ---------------------------------------------------------------------------

def _live_judge(monkeypatch) -> GeminiJudgeClient:
    monkeypatch.setenv("GEMINI_API_KEY", "AIzaSentinelTestKey1234567890")
    return GeminiJudgeClient(live=True)


def test_judge_well_formed_json_verdict(monkeypatch) -> None:
    judge = _live_judge(monkeypatch)
    calls: dict = {}
    verdict_text = json.dumps({"correct": True, "score": 1.0, "rationale": "matches"})
    _sequenced_urlopen(monkeypatch, [_gen_payload(verdict_text, 50, 12)], calls)

    verdict = judge.judge("q", ("Paris",), "Paris")

    assert verdict.correct is True
    assert verdict.score == 1.0
    assert verdict.rationale == "matches"
    assert verdict.usage.input_tokens == 50
    assert verdict.usage.output_tokens == 12
    assert verdict.usage.estimated is False
    in_rate, out_rate = gemini_api.rates_for(JUDGE_MODEL_ID)
    expected_cost = (50 * in_rate + 12 * out_rate) / 1_000_000
    assert verdict.usage.cost_usd == pytest.approx(expected_cost)
    assert calls["n"] == 1


def test_judge_verdict_wrapped_in_markdown_fences(monkeypatch) -> None:
    judge = _live_judge(monkeypatch)
    calls: dict = {}
    fenced = "```json\n" + json.dumps({"correct": False, "score": 0.2, "rationale": "wrong city"}) + "\n```"
    _sequenced_urlopen(monkeypatch, [_gen_payload(fenced, 40, 10)], calls)

    verdict = judge.judge("q", ("Paris",), "London")

    assert verdict.correct is False
    assert verdict.score == 0.2
    assert verdict.rationale == "wrong city"


def test_judge_malformed_verdict_scores_incorrect_not_skipped(monkeypatch) -> None:
    """Per _parse_verdict's comment: an unparseable reply must be scored
    INCORRECT, not silently skipped — a skip would shrink the denominator and
    hide the damage a broken judge call does to the run."""
    judge = _live_judge(monkeypatch)
    calls: dict = {}
    _sequenced_urlopen(monkeypatch, [_gen_payload("Sure, sounds right to me!", 30, 8)], calls)

    verdict = judge.judge("q", ("Paris",), "Paris")

    assert verdict.correct is False
    assert verdict.score == 0.0
    assert "unparseable" in verdict.rationale
    # still a real, priced usage record — a malformed reply is not a free call
    assert verdict.usage.estimated is False
    assert verdict.usage.input_tokens == 30


def test_judge_retries_on_429_then_succeeds(monkeypatch) -> None:
    judge = _live_judge(monkeypatch)
    calls: dict = {}
    verdict_text = json.dumps({"correct": True, "score": 1.0, "rationale": "ok"})
    _sequenced_urlopen(monkeypatch, [
        _http_error(503, b'{"error": "overloaded"}'),
        _gen_payload(verdict_text, 20, 5),
    ], calls)

    verdict = judge.judge("q", ("a",), "a")

    assert verdict.correct is True
    assert calls["n"] == 2


def test_judge_non_retryable_error_fails_fast(monkeypatch) -> None:
    judge = _live_judge(monkeypatch)
    calls: dict = {}
    _sequenced_urlopen(monkeypatch, [
        _http_error(403, b'{"error": "forbidden"}'),
    ], calls)

    with pytest.raises(RuntimeError, match="HTTP 403"):
        judge.judge("q", ("a",), "a")

    assert calls["n"] == 1
