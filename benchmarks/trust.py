"""
privacy-audit: allow-file "Trust axis scorer references sub-criterion names + example thresholds; no user data."

Trust axis — deterministic scorer.

Sub-criteria mirror benchmarks/RUBRIC.md §Axis 4.

Per the rubric, the trust axis score produced here is provisional. The
final published score in docs/BENCHMARK_REPORT.md must come from an
independent Opus security-audit pass that may *lower* (never raise) this
draft.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def _read(rel: str) -> str:
    p = REPO / rel
    return p.read_text(errors="ignore") if p.exists() else ""


def _ci_runs(command: str) -> bool:
    """Whether any workflow actually invokes `command`.

    Checked by content rather than by workflow filename. Both callers below
    previously looked for a specific file (test.yml, version-consistency.yml);
    CI was later consolidated into a single shr-verify.yml, so both reported
    False and capped their sub-scores while CI was in fact running those
    commands on every pull request. A filename is not evidence — the step is.
    """
    workflows = REPO / ".github" / "workflows"
    if not workflows.is_dir():
        return False
    return any(
        command in path.read_text(encoding="utf-8", errors="ignore")
        for path in sorted(workflows.glob("*.y*ml"))
    )


def _score_version_consistency() -> tuple[float, str]:
    script = REPO / "scripts" / "check-version-consistency.py"
    if not script.exists():
        return 0.0, "checker missing"
    r = subprocess.run(
        [sys.executable, str(script), "--root", str(REPO)],
        capture_output=True, text=True,
    )
    ci_enforced = _ci_runs("check-version-consistency")
    if r.returncode != 0:
        return 4.0, f"checker exits non-zero: {r.stdout[-200:]}"
    score = 10.0 if ci_enforced else 8.0
    return score, f"checker clean; ci_enforced={ci_enforced}"


def _score_test_suite() -> tuple[float, str]:
    tests_dir = REPO / "tests"
    if not tests_dir.exists():
        return 0.0, "tests/ missing"
    test_files = list(tests_dir.glob("test_*.py"))
    has_pytest_ini = (REPO / "pytest.ini").exists()
    has_test_workflow = _ci_runs("pytest")
    # We don't run coverage here (slow); we credit it via workflow existence
    score = 10.0 if (len(test_files) >= 6 and has_pytest_ini and has_test_workflow) else \
            8.0 if len(test_files) >= 5 else \
            5.0 if len(test_files) >= 2 else 2.0
    return score, f"{len(test_files)} test files; pytest.ini={has_pytest_ini}; ci={has_test_workflow}"


def _score_privacy_patterns() -> tuple[float, str]:
    from shiroe.privacy import _PROVIDER_PATTERNS  # type: ignore
    n = len(_PROVIDER_PATTERNS)
    score = 10.0 if n >= 9 else 7.0 if n >= 5 else 4.0
    return score, f"{n} provider-shaped credential patterns wired"


def _score_security_md() -> tuple[float, str]:
    text = _read("SECURITY.md")
    if not text:
        return 0.0, "SECURITY.md missing"
    no_public_route = "Do not open a public GitHub issue" in text
    private_pvr = "Private Vulnerability Reporting" in text
    pgp = "PGP" in text or "SECURITY_CONTACTS.md" in text
    window = "90-day" in text or "90 day" in text
    have = sum([no_public_route, private_pvr, pgp, window])
    score = 10.0 if have == 4 else 8.0 if have == 3 else 5.0 if have == 2 else 2.0
    return score, (
        f"no_public_route={no_public_route}, pvr={private_pvr}, "
        f"pgp={pgp}, window={window}"
    )


def _score_ci_hardening() -> tuple[float, str]:
    workflow_dir = REPO / ".github" / "workflows"
    if not workflow_dir.exists():
        return 0.0, "no workflows"
    floating = 0
    sha_pinned = 0
    for wf in workflow_dir.glob("*.yml"):
        text = wf.read_text(errors="ignore")
        for m in re.finditer(r"uses:\s*([^\s]+)@([^\s]+)", text):
            ref = m.group(2)
            if re.fullmatch(r"[0-9a-f]{40}", ref):
                sha_pinned += 1
            elif ref.startswith("v") or "." in ref:
                floating += 1
    dependabot = (REPO / ".github" / "dependabot.yml").exists()
    total = sha_pinned + floating
    pct = (sha_pinned / total) if total else 0
    score = 10.0 if (pct >= 0.99 and dependabot) else \
            8.0 if (pct >= 0.99) else \
            6.0 if pct >= 0.5 else 3.0
    return score, (
        f"{sha_pinned}/{total} action refs SHA-pinned "
        f"({pct*100:.0f}%); dependabot={dependabot}"
    )


def run() -> dict:
    subs = {
        "version_consistency":  _score_version_consistency(),
        "test_suite":           _score_test_suite(),
        "privacy_patterns":     _score_privacy_patterns(),
        "security_md":          _score_security_md(),
        "ci_hardening":         _score_ci_hardening(),
    }
    axis = sum(s for s, _ in subs.values()) / len(subs)
    return {
        "axis": "trust",
        "score": round(axis, 2),
        "sub": {k: {"score": round(s, 2), "evidence": e} for k, (s, e) in subs.items()},
        "note": (
            "Deterministic trust scorer. Use an independent high-effort "
            "security review before making any public final trust verdict."
        ),
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
