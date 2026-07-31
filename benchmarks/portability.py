"""
Portability axis — deterministic scorer.

Sub-criteria mirror benchmarks/RUBRIC.md §Axis 1. Each sub-criterion
returns a 0–10 sub-score; the axis score is the weighted average.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def _score_agents_md() -> tuple[float, str]:
    p = REPO / "AGENTS.md"
    if not p.exists():
        return 0.0, "AGENTS.md missing"
    stubs = ["CLAUDE.md", "CODEX.md", "GEMINI.md", "LLAMA.md",
             ".windsurfrules", ".aider.conf.yml.example",
             ".cursor/rules/shiroe.mdc"]
    cite_count = sum(
        1 for s in stubs
        if (REPO / s).exists()
        and "AGENTS.md" in (REPO / s).read_text(errors="ignore")
    )
    score = 10.0 if cite_count >= 6 else 7.0 if cite_count >= 4 else 4.0
    return score, f"AGENTS.md present; {cite_count}/{len(stubs)} stubs cite it"


def _score_stubs() -> tuple[float, str]:
    required = ["CLAUDE.md", "CODEX.md", "GEMINI.md", "LLAMA.md",
                ".windsurfrules", ".aider.conf.yml.example",
                ".cursor/rules/shiroe.mdc"]
    present = [s for s in required if (REPO / s).exists()]
    n = len(present)
    score = 10.0 if n >= 7 else 8.0 if n >= 5 else 6.0 if n >= 3 else 2.0
    return score, f"{n}/{len(required)} harness stubs present: {present}"


def _score_probe() -> tuple[float, str]:
    probe = REPO / "scripts" / "harness-probe.py"
    if not probe.exists():
        return 0.0, "harness-probe.py missing"
    r = subprocess.run(
        [sys.executable, str(probe), "--json"],
        capture_output=True, text=True, cwd=str(REPO),
    )
    if r.returncode != 0:
        return 4.0, f"harness-probe crashed: {r.stderr.strip()}"
    try:
        data = json.loads(r.stdout)
        n = sum(1 for h in data["harnesses"] if h["stub_ok"])
        total = len(data["harnesses"])
        score = 10.0 if n == total else 8.0 if n >= total - 2 else 6.0
        return score, f"probe ran clean; {n}/{total} stubs present"
    except Exception as e:  # pragma: no cover
        return 5.0, f"probe output unparseable: {e}"


def _score_matrix() -> tuple[float, str]:
    p = REPO / "docs" / "HARNESS_MATRIX.md"
    if not p.exists():
        return 0.0, "HARNESS_MATRIX.md missing"
    text = p.read_text(errors="ignore")
    n_rows = text.count("\n| ") - 1  # subtract header separator
    score = 10.0 if n_rows >= 6 else 7.0 if n_rows >= 3 else 4.0
    return score, f"HARNESS_MATRIX.md has ~{n_rows} harness rows"


def _score_cli() -> tuple[float, str]:
    r = subprocess.run(
        [sys.executable, "-m", "shiroe", "--version"],
        capture_output=True, text=True, cwd=str(REPO),
    )
    if r.returncode != 0:
        return 0.0, f"CLI --version crashed: {r.stderr.strip()}"
    r2 = subprocess.run(
        [sys.executable, "-m", "shiroe", "status"],
        capture_output=True, text=True, cwd=str(REPO),
    )
    if r2.returncode != 0:
        return 5.0, f"CLI status crashed: {r2.stderr.strip()}"
    return 10.0, "CLI --version and status both clean"


def run() -> dict:
    subs = {
        "canonical_agents_md": _score_agents_md(),
        "per_harness_stubs":   _score_stubs(),
        "harness_probe":       _score_probe(),
        "harness_matrix":      _score_matrix(),
        "cli_works":           _score_cli(),
    }
    # all weights equal (2 each); axis = mean
    axis = sum(s for s, _ in subs.values()) / len(subs)
    return {
        "axis": "portability",
        "score": round(axis, 2),
        "sub": {k: {"score": round(s, 2), "evidence": e} for k, (s, e) in subs.items()},
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
