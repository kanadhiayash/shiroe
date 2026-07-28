#!/usr/bin/env python3
"""
privacy-audit: allow-file "Benchmark harness names axis IDs + example evidence fields; no user data."

benchmarks/run-all.py — Run all INTERNAL QUALITY AXES and emit
docs/BENCHMARK_REPORT.md plus machine-readable benchmarks/results.json.

These axes are fixture-based self-checks of local invariants. They are NOT
external benchmark results and must never be presented as rankings against
other systems. External-dataset benchmarking lives under benchmarks/external/.

Exit code:
    0  every scored axis ≥ 9.0 (the internal pass bar); skipped axes ignored
    1  otherwise
Skipped axes (e.g. missing lineage intake CSV on a clean clone) are recorded
explicitly in the report and results.json and do NOT inflate the
passed-verdict (see ZRF-AUDIT-012).

Usage:
    python3 benchmarks/run-all.py
    python3 benchmarks/run-all.py --rubric benchmarks/RUBRIC.md
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from benchmarks import (  # noqa: E402
    adaptivity,
    adapter_value,
    contradiction_detection,
    critical_adoption_coverage,
    foreign_code_containment,
    handoff_success,
    high_adoption_coverage,
    license_boundary,
    lineage_import_coverage,
    loop_control,
    memory_refinement,
    minimality_pressure,
    portability,
    privacy_safety,
    prompt_rewrite_quality,
    reference_only_guardrails,
    retrieval,
    retrieval_accuracy,
    scalability,
    security_containment,
    token_efficiency,
    trust,
)
from zeref.benchmark.failure_analysis import collect_failures, write_failure_report  # noqa: E402

AXES = [
    portability,
    adaptivity,
    scalability,
    retrieval,
    trust,
    token_efficiency,
    retrieval_accuracy,
    contradiction_detection,
    privacy_safety,
    prompt_rewrite_quality,
    handoff_success,
    loop_control,
    memory_refinement,
    lineage_import_coverage,
    foreign_code_containment,
    critical_adoption_coverage,
    high_adoption_coverage,
    reference_only_guardrails,
    adapter_value,
    minimality_pressure,
    security_containment,
    license_boundary,
]


def _apply_verified_overrides(results: list[dict]) -> list[dict]:
    """Apply independent audit overrides that may lower deterministic drafts.

    Refuses the override unless docs/TRUST_AUDIT.md carries a Bound-commit-SHA
    equal to the current HEAD. Prevents stale trust scores from silently applying
    to newer code (see ZRF-AUDIT-013).
    """
    trust_audit = REPO / "docs" / "TRUST_AUDIT.md"
    if not trust_audit.exists():
        return results

    text = trust_audit.read_text(encoding="utf-8", errors="ignore")
    match = re.search(
        r"^- \*\*Verified score \(this audit\):\*\* \*\*([0-9]+(?:\.[0-9]+)?)\*\*",
        text,
        re.MULTILINE,
    )
    if not match:
        return results

    # SHA-binding gate: audit must name the commit it graded.
    sha_match = re.search(
        r"^- \*\*Bound-commit-SHA:\*\* `([0-9a-f]{7,40})`",
        text,
        re.MULTILINE,
    )
    if not sha_match:
        # No SHA binding — refuse override, keep deterministic draft.
        return results
    bound_sha = sha_match.group(1)
    try:
        import subprocess
        head_sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPO, text=True
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        head_sha = ""
    if head_sha and not head_sha.startswith(bound_sha):
        # HEAD moved since the independent audit; refuse override.
        for result in results:
            if result.get("axis") == "trust":
                result.setdefault("note", (
                    f"TRUST_AUDIT.md Bound-commit-SHA {bound_sha} does not match HEAD "
                    f"{head_sha[:12]}; deterministic draft score published (see ZRF-AUDIT-013)."
                ))
        return results

    verified_trust = float(match.group(1))
    adjusted: list[dict] = []
    for result in results:
        if result.get("axis") != "trust":
            adjusted.append(result)
            continue

        published = dict(result)
        draft_score = float(result["score"])
        if verified_trust <= draft_score:
            published["draft_score"] = draft_score
            published["score"] = round(verified_trust, 2)
            published["summary_note"] = (
                f"Verified by TRUST_AUDIT.md; deterministic draft was {draft_score:.2f}."
            )
            published["note"] = (
                f"Deterministic draft score was {draft_score:.2f}. "
                f"Published trust score is {verified_trust:.2f} per "
                "docs/TRUST_AUDIT.md independent audit."
            )
        adjusted.append(published)
    return adjusted


def _render_report(results: list[dict], rubric_rel: str, passed: bool, failures: list[dict]) -> str:
    today = date.today().isoformat()  # noqa: DTZ011 — public report only
    lines = [
        "# Internal Quality Axes Report - Zeref Memory Engine",
        "",
        "> **Internal quality axes — fixture-based self-checks. NOT external benchmark results.**",
        "> These axes verify local invariants against committed fixtures. They do not measure",
        "> performance on any external dataset and must not be quoted as benchmark scores.",
        "> External-dataset benchmarking lives in [`benchmarks/external/`](../benchmarks/external/README.md);",
        "> no external scores are claimed until full-dataset runs are published.",
        "",
        f"_Generated: {today}. Rubric: [`{rubric_rel}`]({rubric_rel})._",
        "",
        "## Verdict",
        "",
        ("**PASS** - deterministic internal quality gates passed."
         if passed else
         "**FAIL** - at least one deterministic internal quality gate failed."),
        "",
        "This report is local and deterministic. It does not claim external superiority, production readiness, or a final perfect-score verdict.",
        "",
        ("The `trust` axis is independently re-graded by the security audit "
         "before publication. When the audit score is lower than the "
         "deterministic draft, the verified score is the published score."),
        "",
        ("Lineage axes validate local intake metadata, implementation registries, "
         "and guardrails. They are not external-dataset verification of the "
         "referenced projects."),
        "",
        "## Scores",
        "",
        "| Axis | Score | Status | Note |",
        "|---|---:|---|---|",
    ]
    for r in results:
        if r.get("skipped"):
            lines.append(f"| {r['axis']} | — | SKIPPED | {r.get('reason', 'skipped')} |")
            continue
        ok = "pass" if r["score"] >= 9.0 else ("review" if r["score"] >= 8.0 else "fail")
        note = r.get("summary_note", "")
        lines.append(f"| {r['axis']} | {r['score']:.2f} | {ok} | {note} |")
    lines.append("")

    skipped_axes = [r for r in results if r.get("skipped")]
    if skipped_axes:
        lines += [
            "## Skipped axes",
            "",
            "Skipped axes are reported explicitly and never count as passing evidence.",
            "",
        ]
        for r in skipped_axes:
            lines.append(f"- `{r['axis']}`: {r.get('reason', 'skipped')}")
        lines.append("")

    if failures:
        lines += [
            "## Failure Summary",
            "",
            "| Failed metric | Expected | Actual | Needed fix |",
            "|---|---|---|---|",
        ]
        for failure in failures:
            lines.append(
                f"| `{failure['failed_metric']}` | {failure['expected']} | "
                f"{failure['actual']} | {failure['needed_fix']} |"
            )
        lines.append("")

    for r in results:
        if r.get("skipped"):
            lines += [
                f"## {r['axis'].replace('_', ' ').title()} - SKIPPED",
                "",
                f"> _{r.get('reason', 'skipped')}_",
                "",
            ]
            continue
        lines += [
            f"## {r['axis'].replace('_', ' ').title()} - {r['score']:.2f} / 10",
            "",
            "| Sub-criterion | Score | Evidence |",
            "|---|---:|---|",
        ]
        for k, v in r["sub"].items():
            lines.append(f"| `{k}` | {v['score']:.2f} | {v['evidence']} |")
        if "note" in r:
            lines += ["", f"> _{r['note']}_", ""]
        lines.append("")

    lines += [
        "## How to reproduce",
        "",
        "```bash",
        "python3 benchmarks/run-all.py",
        "```",
        "",
        "Per-axis scorers under `benchmarks/` are standalone:",
        "",
        "```bash",
        "python3 -m benchmarks.portability",
        "python3 -m benchmarks.adaptivity",
        "python3 -m benchmarks.scalability",
        "python3 -m benchmarks.retrieval",
        "python3 -m benchmarks.trust",
        "python3 -m benchmarks.token_efficiency",
        "python3 -m benchmarks.retrieval_accuracy",
        "python3 -m benchmarks.contradiction_detection",
        "python3 -m benchmarks.privacy_safety",
        "python3 -m benchmarks.prompt_rewrite_quality",
        "python3 -m benchmarks.handoff_success",
        "python3 -m benchmarks.loop_control",
        "python3 -m benchmarks.memory_refinement",
        "python3 -m benchmarks.lineage_import_coverage",
        "python3 -m benchmarks.foreign_code_containment",
        "python3 -m benchmarks.critical_adoption_coverage",
        "python3 -m benchmarks.high_adoption_coverage",
        "python3 -m benchmarks.reference_only_guardrails",
        "python3 -m benchmarks.adapter_value",
        "python3 -m benchmarks.minimality_pressure",
        "python3 -m benchmarks.security_containment",
        "python3 -m benchmarks.license_boundary",
        "```",
        "",
        "## Rubric",
        "",
        f"Sub-criteria and weights: [`{rubric_rel}`]({rubric_rel}).",
        "External re-scoring invited via PR.",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rubric", default="benchmarks/RUBRIC.md")
    ap.add_argument("--out-report", default="docs/BENCHMARK_REPORT.md")
    ap.add_argument("--out-json", default="benchmarks/results.json")
    args = ap.parse_args()

    results = _apply_verified_overrides([axis.run() for axis in AXES])

    scored = [r for r in results if not r.get("skipped")]
    failures = collect_failures(scored)
    passed = not failures

    report = _render_report(results, args.rubric, passed, failures)
    (REPO / args.out_report).write_text(report, encoding="utf-8")
    failure_report = write_failure_report(REPO, failures)
    (REPO / args.out_json).write_text(
        json.dumps({
            "label": "internal quality axes — fixture-based self-checks, not external benchmarks",
            # ZRF-66 / issue #172: machine-readable evidence class, so any
            # consumer (claim gate, docs generator) can tell at a glance this
            # is NOT external_benchmark evidence without parsing prose.
            "evidence_namespace": "conformance",
            "evidence_tier": "fixture_tested",
            "passed": passed,
            "pass_bar": {"axis_min": 9.0},
            "axes": results,
            "skipped_axes": [r["axis"] for r in results if r.get("skipped")],
            "failures": failures,
            "failure_report": str(failure_report.relative_to(REPO)),
        }, indent=2),
        encoding="utf-8",
    )

    for r in results:
        if r.get("skipped"):
            print(f"{r['axis']:<14} SKIPPED ({r.get('reason', '')[:60]}...)")
        else:
            print(f"{r['axis']:<14} {r['score']:.2f}")
    print("-" * 24)
    print("VERDICT:", "PASS" if passed else "FAIL",
          "(internal quality axes; not external benchmark results)")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
