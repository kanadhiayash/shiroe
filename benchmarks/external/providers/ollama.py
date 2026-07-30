"""
privacy-audit: allow-file "Provider names a localhost endpoint and env-var names as spec; no credential values, no user data."

Local Ollama generation provider.

Lets a scored run be generated entirely on-device, at zero cost and with no
quota, so a free Gemini key can be spent solely on judging the cases
deterministic scoring cannot decide.

Why this exists rather than reusing the hosted providers:

* **Cost.** Every call is $0. `estimate()` reports that honestly instead of
  inventing a price, so the budget gate sees local generation for what it is.
  A fabricated non-zero rate would make the cost ceiling refuse runs that
  cannot cost anything.
* **Judge independence.** A local Llama/Qwen generating and Gemini judging is
  a genuine cross-family pair. When one family does both, the judge is
  scoring its own family's output and absolute scores are not defensible —
  see `providers/gemini.py` and `harness._judge_independence`.

Localhost only: no API key exists, nothing leaves the machine, and there is
no account to bill. `dry_run=True` remains the default anyway, matching
`GeminiProvider` and `AnthropicProvider`, so no test can reach the daemon by
accident.

CONTEXT WINDOW — read before running a long-context ladder. Ollama sizes the
context from available VRAM and will silently fall back to a small default
(4096 on a 16 GB machine) unless `num_ctx` is set. A prompt longer than the
active window is TRUNCATED by the server, not rejected, which would quietly
delete the retrieved evidence and score as a model failure. This provider
therefore sets `num_ctx` explicitly and refuses a prompt it cannot fit —
see `complete()`.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from benchmarks.external.providers.base import Completion, Provider, Usage

DEFAULT_MODEL_ID = "llama3.1:8b"
DEFAULT_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
REQUEST_TIMEOUT_S = 900  # local generation on CPU/GPU is slow; not a hung call

# Same 4-chars-per-token heuristic the other providers estimate with, so a
# cross-provider cost comparison comes from one convention.
CHARS_PER_TOKEN = 4

# Context window requested from the server. Ollama's own default is derived
# from VRAM and is far smaller than the model's advertised window; leaving it
# unset is what causes silent prompt truncation.
DEFAULT_NUM_CTX = 32768


class PromptTooLongError(RuntimeError):
    """Prompt exceeds the configured context window.

    Raised rather than letting the server truncate. A truncated prompt drops
    the retrieved context and produces a wrong answer that looks like a
    retrieval failure, which would be attributed to whichever arm was running.
    """


class OllamaProvider(Provider):
    name = "ollama"

    def __init__(
        self,
        model_id: str = DEFAULT_MODEL_ID,
        dry_run: bool = True,
        *,
        host: str | None = None,
        num_ctx: int = DEFAULT_NUM_CTX,
    ) -> None:
        self.model_id = model_id
        self.dry_run = dry_run
        self.host = (host or DEFAULT_HOST).rstrip("/")
        self.num_ctx = num_ctx
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cost_usd = 0.0

    # --- readiness -----------------------------------------------------------

    def available(self) -> bool:
        """Whether the local daemon answers. Never raises."""
        try:
            with urllib.request.urlopen(f"{self.host}/api/version", timeout=5):
                return True
        except (urllib.error.URLError, TimeoutError, OSError):
            return False

    def installed_models(self) -> list[str]:
        """Model tags the daemon has locally. Empty when unreachable."""
        try:
            with urllib.request.urlopen(f"{self.host}/api/tags", timeout=10) as response:
                payload = json.loads(response.read())
        except (urllib.error.URLError, TimeoutError, OSError, ValueError):
            return []
        return [model["name"] for model in payload.get("models", []) if "name" in model]

    # --- estimation ----------------------------------------------------------

    def estimate(self, prompt: str, expected_output_tokens: int = 256) -> Usage:
        """Token estimate at zero cost.

        `cost_usd` is 0.0 because local inference is free. `estimated=True`
        because the token counts are a heuristic, not the server's own
        accounting — `complete()` reports the real counts.
        """
        input_tokens = max(1, len(prompt) // CHARS_PER_TOKEN)
        usage = Usage(
            input_tokens=input_tokens,
            output_tokens=expected_output_tokens,
            cost_usd=0.0,
            estimated=True,
        )
        self.total_input_tokens += usage.input_tokens
        self.total_output_tokens += usage.output_tokens
        return usage

    # --- generation ----------------------------------------------------------

    def complete(self, prompt: str, max_tokens: int = 512) -> Completion:
        if self.dry_run:
            return Completion(text="", usage=self.estimate(prompt, max_tokens))

        # Reserve room for the reply: num_ctx covers prompt AND completion.
        budget_tokens = self.num_ctx - max_tokens
        estimated_prompt_tokens = len(prompt) // CHARS_PER_TOKEN
        if budget_tokens <= 0 or estimated_prompt_tokens > budget_tokens:
            raise PromptTooLongError(
                f"prompt is ~{estimated_prompt_tokens} tokens but only {budget_tokens} "
                f"fit alongside a {max_tokens}-token reply in num_ctx={self.num_ctx}. "
                "Raise num_ctx (VRAM permitting), lower --recall-k, or record this "
                "context length as infeasible for this arm — do not let the server "
                "truncate, which silently drops the retrieved evidence."
            )

        body = json.dumps({
            "model": self.model_id,
            "prompt": prompt,
            "stream": False,
            "options": {
                # Deterministic: an arm comparison needs the generator to be
                # the same function on every call.
                "temperature": 0.0,
                "seed": 0,
                "num_predict": max_tokens,
                "num_ctx": self.num_ctx,
            },
        }).encode("utf-8")

        request = urllib.request.Request(
            f"{self.host}/api/generate",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_S) as response:
                payload = json.loads(response.read())
        except urllib.error.HTTPError as exc:
            detail = exc.read(2048).decode("utf-8", "replace") if exc.fp else ""
            raise RuntimeError(f"Ollama generate failed — HTTP {exc.code}: {detail[:300]}") from None
        except (urllib.error.URLError, TimeoutError) as exc:
            raise RuntimeError(
                f"Ollama generate failed — {exc}. Is the daemon running at {self.host}?"
            ) from None

        # Real counts from the server, so usage is not an estimate. The cost
        # stays 0.0: there is nothing to bill for a local model.
        input_tokens = int(payload.get("prompt_eval_count", 0))
        output_tokens = int(payload.get("eval_count", 0))
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        return Completion(
            text=payload.get("response", ""),
            usage=Usage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=0.0,
                estimated=False,
            ),
        )
