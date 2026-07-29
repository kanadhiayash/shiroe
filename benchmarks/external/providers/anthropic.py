"""
privacy-audit: allow-file "Provider adapter names the API-key env var and pricing schema as spec; no credential values, no user data."

Anthropic provider adapter with live inference.

Reads ANTHROPIC_API_KEY from the environment (never printed, never included
in an error message) and records cost per call. ``dry_run=True`` is the
DEFAULT: it estimates token counts without touching the API, so tests and
proxy runs can never bill. A live call needs ``dry_run=False`` AND a key.

The key is sent as an ``x-api-key`` header, never a URL parameter, because
urllib embeds the request URL in every HTTPError/URLError string and that is
where a key would otherwise leak into a traceback or a CI log.
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

from benchmarks.external.providers.base import Completion, Provider, Usage

DEFAULT_MODEL_ID = "claude-sonnet-4-5"

API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
REQUEST_TIMEOUT_S = 120
MAX_RETRIES = 3
RETRY_BACKOFF_S = 1.5
# 429 and 5xx are transient. 400/401/403 are not, and must fail fast rather
# than burning three doomed retries against a bad key.
RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504, 529})

# List pricing (USD per million tokens: input, output). Verify against current
# published pricing before quoting any dollar figure publicly.
PRICING_USD_PER_MTOK: dict[str, tuple[float, float]] = {
    "claude-sonnet-4-5": (3.0, 15.0),
    "claude-haiku-4-5": (1.0, 5.0),
    "claude-opus-4-1": (15.0, 75.0),
}

# An unpriced model bills at the most expensive known rate, so an unknown
# model over-estimates and trips the budget ceiling early rather than silently
# under-charging the estimate that authorises a run.
_UNKNOWN_MODEL_RATES = (15.0, 75.0)

# Rough chars-per-token heuristic for dry-run estimates (no tokenizer, no API).
CHARS_PER_TOKEN = 4

_SSL_CONTEXT: "ssl.SSLContext | None" = None


def _rates_for(model_id: str) -> tuple[float, float]:
    """Price a model, failing expensive rather than cheap when unknown."""
    return PRICING_USD_PER_MTOK.get(model_id, _UNKNOWN_MODEL_RATES)


def _ssl_context() -> "ssl.SSLContext":
    """A verifying TLS context, with an explicit CA bundle if one is needed.

    Some python.org macOS builds ship without a configured trust store and
    fail CERTIFICATE_VERIFY_FAILED against every host. Verification is NEVER
    disabled — this connection carries an API key.
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
    """Strip anything key-shaped from text bound for an exception or log."""
    text = re.sub(r"sk-ant-[0-9A-Za-z_\-]{10,}", "[REDACTED-KEY]", text)
    text = re.sub(
        r"(?i)(x-api-key|key|token|authorization)[=:\s]+[^&\s\"']+",
        r"\1=[REDACTED]",
        text,
    )
    return text[:500]


class AnthropicProvider(Provider):
    name = "anthropic"

    def __init__(self, model_id: str = DEFAULT_MODEL_ID, dry_run: bool = True) -> None:
        self.model_id = model_id
        self.dry_run = dry_run
        self.api_key = os.environ.get("ANTHROPIC_API_KEY")
        self.total_cost_usd = 0.0
        self.total_input_tokens = 0
        self.total_output_tokens = 0

    def has_key(self) -> bool:
        """Whether a key was found. Never exposes the value."""
        return bool(self.api_key)

    def estimate(self, prompt: str, expected_output_tokens: int = 256) -> Usage:
        input_tokens = max(1, len(prompt) // CHARS_PER_TOKEN)
        in_rate, out_rate = _rates_for(self.model_id)
        cost = (input_tokens * in_rate + expected_output_tokens * out_rate) / 1_000_000
        usage = Usage(
            input_tokens=input_tokens,
            output_tokens=expected_output_tokens,
            cost_usd=cost,
            estimated=True,
        )
        self._record(usage)
        return usage

    def complete(self, prompt: str, max_tokens: int = 512) -> Completion:
        """Generate one answer.

        ``dry_run=True`` (the default) returns an empty completion priced by
        estimate() and makes no network call, so tests and proxy runs can
        never bill.
        """
        if self.dry_run:
            return Completion(text="", usage=self.estimate(prompt))
        if not self.api_key:
            raise RuntimeError(
                "no ANTHROPIC_API_KEY in the environment; cannot run live "
                "inference. (The key value is never printed by this client.)"
            )

        body = json.dumps({
            "model": self.model_id,
            "max_tokens": max_tokens,
            # Deterministic generation: a provider that varies run to run makes
            # two arms incomparable, which defeats the three-arm design.
            "temperature": 0.0,
            "messages": [{"role": "user", "content": prompt}],
        }).encode("utf-8")

        payload = self._post(body)
        text = "".join(
            block.get("text", "")
            for block in payload.get("content", [])
            if block.get("type") == "text"
        )
        return Completion(text=text, usage=self._usage_from_response(payload))

    def _post(self, body: bytes) -> dict:
        """POST to the Messages API, retrying only transient failures."""
        request = urllib.request.Request(
            API_URL,
            data=body,
            headers={
                "content-type": "application/json",
                "x-api-key": self.api_key or "",
                "anthropic-version": ANTHROPIC_VERSION,
                "User-Agent": "zeref-benchmark-provider/1.0",
            },
            method="POST",
        )
        last_error = ""
        for attempt in range(MAX_RETRIES):
            try:
                with urllib.request.urlopen(
                    request, timeout=REQUEST_TIMEOUT_S, context=_ssl_context()
                ) as response:
                    return json.loads(response.read())
            except urllib.error.HTTPError as exc:
                detail = exc.read(2048).decode("utf-8", "replace") if exc.fp else ""
                last_error = f"HTTP {exc.code}: {_redact(detail)}"
                if exc.code not in RETRYABLE_STATUS:
                    raise RuntimeError(f"Anthropic call failed — {last_error}") from None
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                last_error = _redact(str(exc))
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_BACKOFF_S * (2 ** attempt))
        raise RuntimeError(
            f"Anthropic call failed after {MAX_RETRIES} attempts — {last_error}"
        ) from None

    def _usage_from_response(self, payload: dict) -> Usage:
        """Real token counts from the API, priced at the local table."""
        meta = payload.get("usage", {})
        input_tokens = int(meta.get("input_tokens", 0))
        output_tokens = int(meta.get("output_tokens", 0))
        in_rate, out_rate = _rates_for(self.model_id)
        usage = Usage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=(input_tokens * in_rate + output_tokens * out_rate) / 1_000_000,
            estimated=False,
        )
        self._record(usage)
        return usage

    def _record(self, usage: Usage) -> None:
        self.total_cost_usd += usage.cost_usd
        self.total_input_tokens += usage.input_tokens
        self.total_output_tokens += usage.output_tokens
