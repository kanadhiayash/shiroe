from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from zeref.benchmark.failure_analysis import collect_failures, write_failure_report


NEW_AXES = [
    "token_efficiency",
    "retrieval_accuracy",
    "contradiction_detection",
    "privacy_safety",
    "prompt_rewrite_quality",
    "handoff_success",
    "loop_control",
    "memory_refinement",
]


def test_new_benchmark_axes_are_standalone(repo_root: Path) -> None:
    for axis in NEW_AXES:
        result = subprocess.run(
            [sys.executable, "-m", f"benchmarks.{axis}"],
            capture_output=True,
            text=True,
            cwd=str(repo_root),
        )
        assert result.returncode == 0, f"{axis} failed:\n{result.stdout}\n{result.stderr}"
        payload = json.loads(result.stdout)
        assert payload["axis"] == axis
        assert payload["score"] >= 9.0


def test_failure_analysis_contains_required_fields(tmp_path: Path) -> None:
    failures = collect_failures([
        {
            "axis": "example_axis",
            "score": 7.5,
            "sub": {
                "example": {"score": 5.0, "evidence": "missing fixture"},
            },
        }
    ])
    assert failures
    for key in [
        "failed_metric",
        "expected",
        "actual",
        "likely_cause",
        "needed_fix",
        "regression_test_suggestion",
    ]:
        assert key in failures[0]

    path = write_failure_report(tmp_path, failures)
    text = path.read_text(encoding="utf-8")
    assert "Expected:" in text
    assert "Actual:" in text
    assert "Likely cause:" in text
    assert "Needed fix:" in text
    assert "Regression-test suggestion:" in text


def test_axis_evidence_is_machine_independent_and_stable() -> None:
    """Generated axis evidence must carry no absolute paths and no random ids.

    `benchmarks/run-all.py` writes every axis's evidence strings into
    `benchmarks/results.json` and `docs/BENCHMARK_REPORT.md`, both TRACKED in
    a public repository. Two failure modes were live before this test:

      * an absolute path leaked the operator's home directory into a public
        file on every local run (REDACT.md `internal_paths`);
      * random atom/loop ids made the artifacts differ on every run, so the
        worktree was permanently dirty and no clean-tree gate could pass.

    Both are regressions in reproducibility as much as in privacy, so this
    asserts the axes directly rather than the rendered report.
    """
    import re

    from benchmarks.lineage_common import intake_skip
    from benchmarks.loop_control import run as loop_control_run
    from benchmarks.retrieval_accuracy import run as retrieval_accuracy_run

    evidence: list[str] = []
    for axis in (retrieval_accuracy_run(), loop_control_run()):
        evidence.extend(sub["evidence"] for sub in axis["sub"].values())
    skip = intake_skip("lineage_import_coverage")
    if skip is not None:  # absent only when the local-only intake CSV exists
        evidence.append(skip["reason"])

    for text in evidence:
        assert "/Users/" not in text and "/home/" not in text, (
            f"absolute path leaked into tracked benchmark output: {text!r}"
        )
        assert not re.search(r"\b(?:decision|risk|loop|atom)_[0-9a-f]{8,}", text), (
            f"random generated id leaked into tracked benchmark output: {text!r}"
        )


def test_run_all_is_idempotent(repo_root: Path, tmp_path: Path) -> None:
    """Two consecutive `run-all.py` invocations must agree byte for byte.

    Guards the whole pipeline, not just the axes above: any future axis that
    interpolates a timestamp, temp path, or random id would dirty two tracked
    files on every run and is caught here.
    """
    results = repo_root / "benchmarks" / "results.json"
    original = results.read_bytes()
    try:
        digests = []
        for _ in range(2):
            completed = subprocess.run(
                [sys.executable, "benchmarks/run-all.py"],
                cwd=repo_root, capture_output=True, text=True,
            )
            assert completed.returncode == 0, completed.stderr
            digests.append(json.dumps(json.loads(results.read_text(encoding="utf-8")), sort_keys=True))
        assert digests[0] == digests[1], "run-all.py output differs between consecutive runs"
    finally:
        results.write_bytes(original)
