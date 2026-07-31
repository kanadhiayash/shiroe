"""
privacy-audit: allow-file "Tests reference env-var names and fake payloads only; no real credentials, no user data."

Mocked-transport tests for AnthropicProvider.complete(dry_run=False).

Only the no-key refusal path had coverage before this file (see
test_ws5_external_harness.py). The live HTTP path — success parsing, real
usage-derived cost, 429 retry, and fail-fast on a non-retryable error — had
never been exercised at all. Every test here stubs urllib.request.urlopen at
the module boundary, matching tests/test_ollama_provider.py's shape, so
nothing here can make a real network call or spend a real key.
"""

from __future__ import annotations

import io
import json
import urllib.error

import pytest

from benchmarks.external.providers.anthropic import (
    DEFAULT_MODEL_ID,
    PRICING_USD_PER_MTOK,
    AnthropicProvider,
)


class _FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False


def _http_error(code: int, body: bytes = b"{}") -> urllib.error.HTTPError:
    return urllib.error.HTTPError(
        url="https://api.anthropic.com/v1/messages",
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
        "benchmarks.external.providers.anthropic.urllib.request.urlopen", fake_urlopen
    )
    monkeypatch.setattr(
        "benchmarks.external.providers.anthropic.time.sleep", lambda *_: None
    )


def _live_provider(monkeypatch) -> AnthropicProvider:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-sentinel")
    return AnthropicProvider(dry_run=False)


def test_successful_call_parses_text_and_real_usage(monkeypatch) -> None:
    provider = _live_provider(monkeypatch)
    calls: dict = {}
    _sequenced_urlopen(monkeypatch, [
        {"content": [{"type": "text", "text": "Paris."}],
         "usage": {"input_tokens": 41, "output_tokens": 3}},
    ], calls)

    completion = provider.complete("capital of France?")

    assert completion.text == "Paris."
    assert completion.usage.input_tokens == 41
    assert completion.usage.output_tokens == 3
    assert completion.usage.estimated is False
    in_rate, out_rate = PRICING_USD_PER_MTOK[DEFAULT_MODEL_ID]
    expected_cost = (41 * in_rate + 3 * out_rate) / 1_000_000
    assert completion.usage.cost_usd == pytest.approx(expected_cost)
    assert provider.total_input_tokens == 41
    assert provider.total_output_tokens == 3
    assert calls["n"] == 1


def test_retries_on_429_then_succeeds(monkeypatch) -> None:
    provider = _live_provider(monkeypatch)
    calls: dict = {}
    _sequenced_urlopen(monkeypatch, [
        _http_error(429, b'{"error": "rate limited"}'),
        {"content": [{"type": "text", "text": "ok"}],
         "usage": {"input_tokens": 5, "output_tokens": 1}},
    ], calls)

    completion = provider.complete("q")

    assert completion.text == "ok"
    assert calls["n"] == 2  # first attempt failed transiently, second succeeded


def test_non_retryable_error_fails_fast(monkeypatch) -> None:
    provider = _live_provider(monkeypatch)
    calls: dict = {}
    _sequenced_urlopen(monkeypatch, [
        _http_error(401, b'{"error": "bad key"}'),
        {"content": [{"type": "text", "text": "should never be reached"}],
         "usage": {"input_tokens": 1, "output_tokens": 1}},
    ], calls)

    with pytest.raises(RuntimeError, match="HTTP 401"):
        provider.complete("q")

    # exactly one attempt: 401 is not in RETRYABLE_STATUS, so it must not
    # burn retries against a key that will never start working.
    assert calls["n"] == 1
