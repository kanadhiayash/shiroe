"""Benchmark failure analysis report writer."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def collect_failures(results: list[dict[str, Any]], *, axis_threshold: float = 9.0) -> list[dict[str, Any]]:
    failures = []
    for result in results:
        if result["score"] < axis_threshold:
            failures.append(_failure(
                metric=result["axis"],
                expected=f"axis score >= {axis_threshold}",
                actual=f"axis score {result['score']}",
                likely_cause="One or more benchmark sub-criteria are below the deterministic pass bar.",
                needed_fix=f"Inspect the {result['axis']} sub-criteria and implement the missing local behavior.",
                suggestion=f"Add or update a regression test for benchmarks.{result['axis']}.",
            ))
    return failures


def write_failure_report(root: Path | str, failures: list[dict[str, Any]]) -> Path:
    root_path = Path(root)
    out_dir = root_path / "memory" / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "benchmark-failures.md"
    path.write_text(render_failure_report(failures), encoding="utf-8")
    return path


def render_failure_report(failures: list[dict[str, Any]]) -> str:
    lines = ["# Benchmark Failure Analysis", ""]
    if not failures:
        lines.extend(["No benchmark failures detected.", ""])
        return "\n".join(lines)
    for failure in failures:
        lines.extend([
            f"## {failure['failed_metric']}",
            "",
            f"- Expected: {failure['expected']}",
            f"- Actual: {failure['actual']}",
            f"- Likely cause: {failure['likely_cause']}",
            f"- Needed fix: {failure['needed_fix']}",
            f"- Regression-test suggestion: {failure['regression_test_suggestion']}",
            "",
        ])
    return "\n".join(lines)


def _failure(
    *,
    metric: str,
    expected: str,
    actual: str,
    likely_cause: str,
    needed_fix: str,
    suggestion: str,
) -> dict[str, str]:
    return {
        "failed_metric": metric,
        "expected": expected,
        "actual": actual,
        "likely_cause": likely_cause,
        "needed_fix": needed_fix,
        "regression_test_suggestion": suggestion,
    }
