"""
privacy-audit: allow-file "Shared Gemini transport names the API-key env var and pricing schema as spec; no credential values, no user data."

Shared Gemini transport for the judge and the provider.

Both the scoring judge and the generation provider talk to the same API with
the same key, the same TLS requirements and the same redaction rules. This
module holds that one implementation so the security-critical parts — key
reading, header placement, redaction, certificate verification — exist once
and cannot drift apart.

Key handling rules enforced here:
  * the key is read on demand and never stored on any object
  * it travels as an ``x-goog-api-key`` HEADER, never a URL parameter, because
    urllib puts the request URL into every HTTPError/URLError string
  * anything key-shaped is stripped from text bound for an exception or log
  * TLS verification is never disabled
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

REPO = Path(__file__).resolve().parents[2]

API_BASE = "https://generativelanguage.googleapis.com/v1beta"
REQUEST_TIMEOUT_S = 60
MAX_RETRIES = 3
RETRY_BACKOFF_S = 1.5
# 429 rate-limit and 5xx are transient; 400/401/403 are not and must fail fast
# rather than burning the budget on three doomed retries.
RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})

# Rough chars-per-token heuristic for dry-run estimates (no tokenizer, no API).
CHARS_PER_TOKEN = 4

# Paid-tier list pricing (USD per million tokens: input, output), verified
# against https://ai.google.dev/gemini-api/docs/pricing on 2026-07-29.
# Re-verify before quoting cost publicly, and treat any model missing from
# this table as unpriced rather than cheap — see rates_for().
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

_SSL_CONTEXT: "ssl.SSLContext | None" = None


def rates_for(model_id: str) -> tuple[float, float]:
    """Price a model, failing expensive rather than cheap when unknown."""
    return PRICING_USD_PER_MTOK.get(model_id, _UNKNOWN_MODEL_RATES)


def ssl_context() -> "ssl.SSLContext":
    """A verifying TLS context, with an explicit CA bundle if one is needed.

    Some python.org macOS builds ship without a configured trust store, so the
    default context fails CERTIFICATE_VERIFY_FAILED against every host. Fall
    back to certifi's bundle, then the system bundle. Verification is NEVER
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


def redact(text: str) -> str:
    """Strip anything key-shaped from text bound for an exception or log.

    Defence in depth: the key is sent as a header, never a URL parameter, so
    it should never appear here. This is the backstop for an API error body
    that echoes a request back, or a future refactor that reintroduces a query
    parameter.
    """
    text = re.sub(r"AIza[0-9A-Za-z_\-]{10,}", "[REDACTED-KEY]", text)
    text = re.sub(r"(?i)(key|token|authorization)=[^&\s\"']+", r"\1=[REDACTED]", text)
    return text[:500]


def read_api_key() -> str | None:
    """Env var wins; falls back to a gitignored .env.local at the repo root.

    Returns the raw key or None. Callers must NOT retain the return value —
    clients store only a boolean derived from it.
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


def first_text(payload: dict[str, Any]) -> str:
    """Pull the model's text out of a generateContent response."""
    for candidate in payload.get("candidates", []):
        for part in candidate.get("content", {}).get("parts", []):
            if isinstance(part.get("text"), str):
                return part["text"]
    return ""


def post(model_id: str, key: str, body: bytes, *, what: str) -> dict:
    """POST to generateContent, retrying transient failures.

    ``what`` names the caller ("judge", "provider") for the error message.
    The key goes in the ``x-goog-api-key`` HEADER, never the URL, because
    urllib embeds the URL in HTTPError/URLError strings — a key in the query
    string would end up in every traceback and log line.
    """
    url = f"{API_BASE}/models/{model_id}:generateContent"
    request = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": key,
            "User-Agent": f"zeref-benchmark-{what}/1.0",
        },
        method="POST",
    )
    last_error = ""
    for attempt in range(MAX_RETRIES):
        try:
            with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_S, context=ssl_context()) as response:
                return json.loads(response.read())
        except urllib.error.HTTPError as exc:
            # Read the body for the reason, but never echo headers back.
            detail = exc.read(2048).decode("utf-8", "replace") if exc.fp else ""
            last_error = f"HTTP {exc.code}: {redact(detail)}"
            if exc.code not in RETRYABLE_STATUS:
                raise RuntimeError(f"Gemini {what} call failed — {last_error}") from None
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = redact(str(exc))
        if attempt < MAX_RETRIES - 1:
            time.sleep(RETRY_BACKOFF_S * (2 ** attempt))
    raise RuntimeError(
        f"Gemini {what} call failed after {MAX_RETRIES} attempts — {last_error}"
    ) from None
