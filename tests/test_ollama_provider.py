"""
privacy-audit: allow-file "Tests reference localhost URLs and env-var names only; no user data."

Offline tests for the local Ollama generation provider.

Every test here stubs the HTTP transport. None contacts a daemon, so the
suite passes on a machine with no Ollama installed and can never generate
tokens as a side effect of running tests.
"""

from __future__ import annotations

import io
import json
import sys
import urllib.error
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from benchmarks.external.providers.ollama import (  # noqa: E402
    CHARS_PER_TOKEN,
    OllamaProvider,
    PromptTooLongError,
)


class _FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False


def _stub_generate(monkeypatch, payload: dict, captured: dict | None = None):
    def fake_urlopen(request, timeout=None, **kwargs):
        if captured is not None:
            captured["url"] = request.full_url
            if getattr(request, "data", None):
                captured["body"] = json.loads(request.data)
        return _FakeResponse(json.dumps(payload).encode())

    monkeypatch.setattr(
        "benchmarks.external.providers.ollama.urllib.request.urlopen", fake_urlopen
    )


def test_dry_run_is_the_default_and_never_calls_out(monkeypatch) -> None:
    """Matches GeminiProvider/AnthropicProvider: no test can reach the daemon."""
    def explode(*args, **kwargs):
        raise AssertionError("dry run must not open a connection")

    monkeypatch.setattr(
        "benchmarks.external.providers.ollama.urllib.request.urlopen", explode
    )
    provider = OllamaProvider()
    assert provider.dry_run is True
    completion = provider.complete("anything")
    assert completion.text == ""
    assert completion.usage.cost_usd == 0.0


def test_estimate_reports_zero_cost() -> None:
    """Local inference is free, and the budget gate must see that honestly.

    Inventing a non-zero rate would make the cost ceiling refuse runs that
    cannot cost anything.
    """
    usage = OllamaProvider().estimate("x" * (CHARS_PER_TOKEN * 500))
    assert usage.cost_usd == 0.0
    assert usage.input_tokens == 500
    assert usage.estimated is True


def test_live_completion_uses_server_token_counts(monkeypatch) -> None:
    captured: dict = {}
    _stub_generate(
        monkeypatch,
        {"response": "Paris.", "prompt_eval_count": 41, "eval_count": 3},
        captured,
    )
    provider = OllamaProvider(dry_run=False, num_ctx=4096)
    completion = provider.complete("capital of France?", max_tokens=16)

    assert completion.text == "Paris."
    # Real counts from the server, so this is not an estimate...
    assert completion.usage.input_tokens == 41
    assert completion.usage.output_tokens == 3
    assert completion.usage.estimated is False
    # ...but it still costs nothing.
    assert completion.usage.cost_usd == 0.0
    assert provider.total_input_tokens == 41


def test_generation_is_deterministic_and_pins_the_context_window(monkeypatch) -> None:
    """An arm comparison needs one generator behaving identically per call."""
    captured: dict = {}
    _stub_generate(monkeypatch, {"response": "x"}, captured)
    OllamaProvider(dry_run=False, num_ctx=16384).complete("q", max_tokens=64)

    options = captured["body"]["options"]
    assert options["temperature"] == 0.0
    assert options["seed"] == 0
    assert options["num_predict"] == 64
    # num_ctx must be sent explicitly: Ollama otherwise derives a small window
    # from VRAM and silently truncates longer prompts.
    assert options["num_ctx"] == 16384
    assert captured["body"]["stream"] is False


def test_oversized_prompt_is_refused_not_truncated() -> None:
    """Truncation would delete the retrieved context and look like a miss.

    The server drops the overflow silently, so the arm that happened to be
    running would be blamed for a harness problem.
    """
    provider = OllamaProvider(dry_run=False, num_ctx=2048)
    with pytest.raises(PromptTooLongError) as excinfo:
        provider.complete("word " * 5000, max_tokens=512)
    assert "infeasible" in str(excinfo.value)


def test_reply_budget_is_reserved_inside_the_window() -> None:
    """num_ctx covers prompt AND completion, so max_tokens must be reserved."""
    provider = OllamaProvider(dry_run=False, num_ctx=1000)
    # 900 prompt tokens alone would fit in 1000, but not beside a 500-token reply.
    with pytest.raises(PromptTooLongError):
        provider.complete("x" * (CHARS_PER_TOKEN * 900), max_tokens=500)


def test_availability_probe_never_raises(monkeypatch) -> None:
    """Readiness is checked before a run; it must report, not explode."""
    def refuse(*args, **kwargs):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr(
        "benchmarks.external.providers.ollama.urllib.request.urlopen", refuse
    )
    provider = OllamaProvider()
    assert provider.available() is False
    assert provider.installed_models() == []


def test_installed_models_lists_exact_tags(monkeypatch) -> None:
    """Exact tags, so alias drift between runs is detectable."""
    _stub_generate(monkeypatch, {"models": [{"name": "llama3.1:8b"}, {"name": "qwen2.5:7b"}]})
    assert OllamaProvider().installed_models() == ["llama3.1:8b", "qwen2.5:7b"]


def test_cli_routes_provider_ollama_to_the_local_backend() -> None:
    import argparse

    from shiroe import cli_benchmark

    modules = cli_benchmark._load_harness_modules()
    args = argparse.Namespace(provider="ollama", provider_model="qwen2.5:7b", num_ctx=65536)
    provider = cli_benchmark._make_provider(modules, args, dry_run=True)

    assert provider.name == "ollama"
    assert provider.model_id == "qwen2.5:7b"
    assert provider.num_ctx == 65536
    assert provider.dry_run is True
