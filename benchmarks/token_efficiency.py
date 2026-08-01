"""Token efficiency axis for deterministic memory routing.

privacy-audit: allow-file "Scorer references tier names + example token budgets; no user data."
"""

from __future__ import annotations

import sys

from benchmarks.helpers import axis_result, print_json_result
from shiroe.memory.cost_router import estimate_tokens, route_operation


def _score_markdown_guard() -> tuple[float, str]:
    result = route_operation("markdown-rewrite")
    ok = result["executor"] == "blocked"
    return (10.0 if ok else 0.0), f"markdown rewrite executor={result['executor']}"


def _score_minimalism_ladder() -> tuple[float, str]:
    duplicate = route_operation("memory-add", duplicate=True)
    append = route_operation("memory-add", text="Use atoms.")
    patch = route_operation("patch", status_change=True)
    ok = (
        duplicate["ladder_step"] == "link-existing"
        and append["ladder_step"] == "atom-append"
        and patch["ladder_step"] == "atom-patch"
    )
    return (10.0 if ok else 4.0), (
        f"duplicate={duplicate['ladder_step']}, append={append['ladder_step']}, "
        f"patch={patch['ladder_step']}"
    )


def _score_flagship_gate() -> tuple[float, str]:
    result = route_operation("memory-add", public_claim=True)
    ok = result["executor"] == "flagship"
    return (10.0 if ok else 5.0), f"public claim executor={result['executor']}"


def _score_estimator() -> tuple[float, str]:
    first = estimate_tokens("one two three")
    second = estimate_tokens("one two three")
    ok = first == second and first["estimated_tokens"] > 0
    return (10.0 if ok else 4.0), f"estimate={first['estimated_tokens']} deterministic={first == second}"


def _score_target_aware_reduction() -> tuple[float, str]:
    """Phase 16 sub-axis: theoretical token reduction from target-aware skip lists.

    For each profile on disk, compute the reduction ratio when caveman-handoff
    drops sections covered by `already_knows`. Uses a synthetic baseline handoff
    of 3000 tokens broken into ~250 tokens per skippable category. Fail-open
    with score 5.0 when no profiles exist (canary state before Phase 14 land).
    """
    try:
        from shiroe.prompt.target_profile import list_profiles, load_profile
    except ImportError:
        return 5.0, "target_profile loader unavailable"

    profile_ids = list_profiles()
    if not profile_ids:
        return 5.0, "no profiles on disk (pre-v1.2)"

    baseline_tokens = 3000
    per_category_tokens = 250  # empirical estimate; refine after Phase-16 measurement
    ratios: list[float] = []
    detail: list[str] = []
    for pid in profile_ids:
        try:
            p = load_profile(pid)
        except Exception:
            continue
        saved = min(per_category_tokens * len(p.already_knows), baseline_tokens - 200)
        reduction = saved / baseline_tokens
        ratios.append(reduction)
        detail.append(f"{pid}={reduction:.0%}")
    if not ratios:
        return 3.0, "profiles present but none loadable"
    aggregate = sum(ratios) / len(ratios)
    # Score: 15% floor per plan; 30% gets full marks.
    if aggregate >= 0.30:
        score = 10.0
    elif aggregate >= 0.15:
        score = 6.0 + 4.0 * ((aggregate - 0.15) / 0.15)
    else:
        score = max(0.0, 10.0 * (aggregate / 0.15))
    evidence = f"aggregate={aggregate:.0%} across {len(ratios)} profile(s); " + ", ".join(detail)
    return round(score, 2), evidence


def run() -> dict:
    return axis_result("token_efficiency", {
        "markdown_guard": _score_markdown_guard(),
        "minimalism_ladder": _score_minimalism_ladder(),
        "flagship_gate": _score_flagship_gate(),
        "deterministic_estimator": _score_estimator(),
        "target_aware_reduction": _score_target_aware_reduction(),
    })


if __name__ == "__main__":
    sys.exit(print_json_result(run()))
