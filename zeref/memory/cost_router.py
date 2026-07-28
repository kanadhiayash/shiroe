"""Deterministic cost routing and artifact budget checks.

privacy-audit: allow-file "Cost router references model tier names + example token budgets; no user data."
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from zeref.codecs.base import default_token_estimate


DEFAULT_POLICY = {
    "default_executor": "deterministic",
    "default_model_tier": "cheap",
    "deterministic_first": True,
    "max_context_tokens_for_memory_write": 1200,
    "max_output_tokens_for_memory_write": 300,
    "full_markdown_rewrite_requires": "approval_or_render",
    "flagship_requires": [
        "contradiction_resolution",
        "privacy_boundary",
        "public_claim",
        "architecture_migration",
        "benchmark_verdict",
        "irreversible_delete",
    ],
    "forbidden_by_default": [
        "load_all_memory_files",
        "rewrite_entire_memory_folder",
        "summarize_without_source_pointers",
        "silent_conflict_resolution",
    ],
    "artifact_budgets": {
        "hot.md": 700,
        "session_digest": 300,
        "project_digest": 500,
        "handoff_pack": 900,
        "decision_record": 180,
        "memory_atom": 80,
        "contradiction_case": 300,
        "evidence_packet": 400,
    },
}

LADDER = [
    "no-write",
    "link-existing",
    "metadata-update",
    "atom-append",
    "atom-patch",
    "view-render",
    "markdown-rewrite",
    "flagship-review",
]

# Known operations, canonicalized to hyphen-spelling -> dispatch family.
# Forbidden operations are NOT listed here — their validity comes straight
# from policy["forbidden_by_default"] (normalized the same way) so a
# policy-declared forbidden op is always "known" without duplicating names
# in two places.
_OPERATION_ALIASES: dict[str, str] = {
    "markdown-rewrite": "markdown-rewrite",
    "full-markdown-rewrite": "markdown-rewrite",
    "memory-add": "memory-add",
    "atom-append": "memory-add",
    "add": "memory-add",
    "patch": "patch",
    "metadata-update": "patch",
    "atom-patch": "patch",
    "render": "render",
    "view-render": "render",
}


def _canonicalize_operation(operation: str) -> str:
    """Single normalization point: hyphen/underscore spellings collapse to
    one canonical form so they can never diverge again."""
    return operation.strip().lower().replace("_", "-")


def load_policy(root: Path | str = Path(".")) -> dict[str, Any]:
    path = Path(root) / "config" / "COST_POLICY.json"
    if not path.exists():
        return DEFAULT_POLICY
    return {**DEFAULT_POLICY, **json.loads(path.read_text(encoding="utf-8"))}


def estimate_tokens(
    text: str,
    *,
    actual_tokens: int | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    """Layered token estimate — most-accurate-available signal wins.

    1. ``actual_tokens``: real usage a caller read back from a provider
       response. Authoritative, so it is trusted as-is.
    2. A model-family tokenizer, if an optional tokenizer extra is
       installed. Lazily imported; never a hard dependency.
    3. A conservative fallback (see ``codecs.base.default_token_estimate``)
       that takes the max of several signals so it cannot materially
       undercount dense or non-Latin-script text.
    """
    chars = len(text)
    if actual_tokens is not None:
        return {
            "estimated_tokens": actual_tokens,
            "estimated_chars": chars,
            "method": "provider_actual",
        }
    if not text:
        return {"estimated_tokens": 0, "estimated_chars": 0, "method": "empty"}

    tokenizer_name, tokenizer_tokens = _tokenizer_estimate(text, model)
    if tokenizer_tokens is not None:
        return {
            "estimated_tokens": tokenizer_tokens,
            "estimated_chars": chars,
            "method": f"tokenizer:{tokenizer_name}",
        }

    return {
        "estimated_tokens": default_token_estimate(text),
        "estimated_chars": chars,
        "method": "conservative_max_signal",
    }


def _tokenizer_estimate(text: str, model: str | None) -> tuple[str | None, int | None]:
    """Optional-extra tokenizer layer. Returns (name, count) or (None, None)
    when no tokenizer library is installed or it fails to load/encode —
    callers fall back to the conservative estimate in that case."""
    try:
        import tiktoken  # type: ignore  # optional dep, see pyproject [tokenizer] extra
    except ImportError:
        return None, None
    try:
        encoding = tiktoken.encoding_for_model(model) if model else tiktoken.get_encoding("cl100k_base")
        return encoding.name, len(encoding.encode(text))
    except Exception:
        return None, None


def route_operation(
    operation: str,
    *,
    text: str = "",
    approval: bool = False,
    render_mode: bool = False,
    duplicate: bool = False,
    status_change: bool = False,
    public_claim: bool = False,
    contradiction: bool = False,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    policy = policy or DEFAULT_POLICY
    estimate = estimate_tokens(text)

    # 1. Canonicalize once. Every subsequent comparison uses `op` only.
    op = _canonicalize_operation(operation)
    forbidden = {_canonicalize_operation(name) for name in policy["forbidden_by_default"]}

    # 2. Validate against the known-operation set. Unknown operations fail
    #    closed here — they must never reach a dispatch branch and silently
    #    resolve to "no-write" as though nothing needed doing.
    if op not in _OPERATION_ALIASES and op not in forbidden:
        return _decision(
            "blocked",
            "flagship-review",
            estimate,
            f"unknown operation {operation!r} — fails closed, needs review",
        )

    # 3. Global deny.
    if op in forbidden:
        return _decision("blocked", "flagship-review", estimate, "operation forbidden by default")

    # 4. Global safety signals + budgets — evaluated before any
    #    operation-specific dispatch, so no branch below can return a
    #    cheap deterministic step for an oversized or flagged write.
    if public_claim:
        return _decision("flagship", "flagship-review", estimate, "public claim requires high-judgment review")
    if contradiction:
        return _decision("flagship", "flagship-review", estimate, "contradiction requires arbitration")
    if estimate["estimated_tokens"] > policy["max_context_tokens_for_memory_write"]:
        return _decision("mid", "flagship-review", estimate, "input exceeds memory write budget")

    # 5. Operation-specific dispatch. `op` is guaranteed to be a known,
    #    non-forbidden operation at this point, so every family below is
    #    exhaustive — no implicit fallthrough.
    family = _OPERATION_ALIASES[op]
    if family == "markdown-rewrite":
        if not (approval or render_mode):
            return _decision(
                "blocked", "markdown-rewrite", estimate, "markdown rewrite requires approval or render mode"
            )
        return _decision("deterministic", "markdown-rewrite", estimate, "markdown rewrite approved")
    if duplicate:
        return _decision("deterministic", "link-existing", estimate, "duplicate memory should link existing atom")
    if status_change or family == "patch":
        return _decision("deterministic", "atom-patch", estimate, "status or metadata change")
    if family == "memory-add":
        return _decision("deterministic", "atom-append", estimate, "new simple memory atom")
    return _decision("deterministic", "view-render", estimate, "rendered view generation")


def audit_budgets(root: Path | str = Path("."), *, strict: bool = False) -> dict[str, Any]:
    root_path = Path(root)
    policy = load_policy(root_path)
    budgets = policy["artifact_budgets"]
    checks = []
    # Only "hot.md" is a single fixed-path artifact in the flat memory/
    # layout (see AGENTS.md "Memory model"). The other declared budgets
    # (session_digest, project_digest, handoff_pack, decision_record,
    # memory_atom, contradiction_case, evidence_packet) size a *single
    # instance* of a per-event artifact (e.g. one handoff pack, one decision
    # record) that is written to a fresh, timestamped, or per-atom path each
    # time — there is no one file to point at. Mapping them to an aggregate
    # file (e.g. all of memory/DECISIONS.md against the decision_record
    # per-item budget) would be actively wrong, not just approximate, so an
    # unmapped budget fails validation instead of guessing a locator.
    mapping = {
        "hot.md": root_path / "memory" / "hot.md",
    }
    for name, budget in budgets.items():
        path = mapping.get(name)
        if path is None:
            checks.append({
                "artifact": name,
                "path": None,
                "budget": budget,
                "estimated_tokens": None,
                "ok": False,
                "reason": "no locator configured for this artifact budget",
            })
            continue
        if not path.exists():
            continue
        tokens = estimate_tokens(path.read_text(encoding="utf-8"))["estimated_tokens"]
        checks.append({
            "artifact": name,
            "path": str(path),
            "budget": budget,
            "estimated_tokens": tokens,
            "ok": tokens <= budget,
        })
    passed = all(check["ok"] for check in checks)
    return {"passed": passed, "strict": strict, "checks": checks}


def report(root: Path | str = Path(".")) -> dict[str, Any]:
    policy = load_policy(root)
    return {
        "default_executor": policy["default_executor"],
        "default_model_tier": policy["default_model_tier"],
        "deterministic_first": policy["deterministic_first"],
        "ladder": LADDER,
        "artifact_budgets": policy["artifact_budgets"],
    }


def _decision(executor: str, ladder_step: str, estimate: dict[str, Any], reason: str) -> dict[str, Any]:
    return {
        "executor": executor,
        "ladder_step": ladder_step,
        "estimate": estimate,
        "reason": reason,
    }
