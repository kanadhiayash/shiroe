"""Source-authority freshness grading (issue #175).

Direct unit coverage for shiroe.prompt.target_profile.grade_profile_freshness:
the branch a stale `official` profile hard-fails on, the branch a stale
`third_party`/`derived` profile only warns on, the schema-invalid branch,
and the clean-pass branch. tests/test_route_release_doctor.py only exercises
this indirectly through the two real on-disk profiles (both third_party
today), so it never proves the hard-fail path fires at all.
"""

from __future__ import annotations

import os
from datetime import date, timedelta
from pathlib import Path

import pytest

from shiroe.prompt.target_profile import (
    ProfileSchemaError,
    grade_profile_freshness,
    load_profile,
)
from shiroe.release import checks as release_checks

_MINIMAL_FIELDS = """\
target_id: {target_id}
vendor: acme
family: acme-family
variant: v1
source_url: https://example.invalid/{target_id}
source_updated_at: {updated_at}
source_authority: {authority}
last_verified_catalog_sha: deadbeef
system_prompt_tokens: 100
output_style: terse
tool_use_format: json
refusal_signature: n/a
"""


def _write_profile(root: Path, target_id: str, *, updated_at: str, authority: str) -> None:
    d = root / "references" / "target-model-profiles"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{target_id}.md").write_text(
        "---\n" + _MINIMAL_FIELDS.format(
            target_id=target_id, updated_at=updated_at, authority=authority,
        ) + "---\n",
        encoding="utf-8",
    )


_TODAY = date(2026, 7, 27)
_STALE = "2026-01-01"   # >60 days before _TODAY
_FRESH = "2026-07-01"   # <60 days before _TODAY


def test_no_profiles_dir_skips(tmp_path: Path) -> None:
    status, reason = grade_profile_freshness(project_root=tmp_path, today=_TODAY)
    assert status == "skip"
    assert "pre-v1.2" in reason


def test_fresh_official_profile_passes(tmp_path: Path) -> None:
    _write_profile(tmp_path, "model-a", updated_at=_FRESH, authority="official")
    status, reason = grade_profile_freshness(project_root=tmp_path, today=_TODAY)
    assert status == "pass"
    assert "1 profile" in reason


def test_stale_official_profile_hard_fails(tmp_path: Path) -> None:
    _write_profile(tmp_path, "model-a", updated_at=_STALE, authority="official")
    status, reason = grade_profile_freshness(project_root=tmp_path, today=_TODAY)
    assert status == "fail"
    assert "official-source" in reason
    assert "model-a" in reason


def test_stale_third_party_profile_warns_not_fails(tmp_path: Path) -> None:
    _write_profile(tmp_path, "model-a", updated_at=_STALE, authority="third_party")
    status, reason = grade_profile_freshness(project_root=tmp_path, today=_TODAY)
    assert status == "warn"
    assert "model-a" in reason


def test_stale_derived_profile_warns_not_fails(tmp_path: Path) -> None:
    _write_profile(tmp_path, "model-a", updated_at=_STALE, authority="derived")
    status, reason = grade_profile_freshness(project_root=tmp_path, today=_TODAY)
    assert status == "warn"


def test_mixed_official_and_third_party_stale_fails_not_warns(tmp_path: Path) -> None:
    """An official hard-fail must win over a simultaneous third_party warn —
    the gate can't be talked down to a warning by adding a compliant profile."""
    _write_profile(tmp_path, "model-official", updated_at=_STALE, authority="official")
    _write_profile(tmp_path, "model-third-party", updated_at=_STALE, authority="third_party")
    status, reason = grade_profile_freshness(project_root=tmp_path, today=_TODAY)
    assert status == "fail"
    assert "model-official" in reason


def test_invalid_source_authority_value_is_schema_error(tmp_path: Path) -> None:
    _write_profile(tmp_path, "model-a", updated_at=_FRESH, authority="rumor")
    status, reason = grade_profile_freshness(project_root=tmp_path, today=_TODAY)
    assert status == "fail"
    assert "model-a" in reason

    try:
        load_profile("model-a", project_root=tmp_path)
        raise AssertionError("expected ProfileSchemaError")
    except ProfileSchemaError as exc:
        assert "source_authority" in str(exc)


def test_missing_source_authority_field_is_schema_error(tmp_path: Path) -> None:
    d = tmp_path / "references" / "target-model-profiles"
    d.mkdir(parents=True)
    text = "---\n" + _MINIMAL_FIELDS.format(
        target_id="model-a", updated_at=_FRESH, authority="official",
    ).replace("source_authority: official\n", "") + "---\n"
    (d / "model-a.md").write_text(text, encoding="utf-8")
    status, reason = grade_profile_freshness(project_root=tmp_path, today=_TODAY)
    assert status == "fail"
    assert "source_authority" in reason


# ---------------------------------------------------------------------------
# Release-gate level (issue #153): checks.py::_check_target_profiles must now
# fail closed on a missing/unreadable profiles dir, since profiles ship.
# grade_profile_freshness has no `today` override plumbed through the gate,
# so these use real (relative-to-now) dates instead of the _TODAY fixture.
# ---------------------------------------------------------------------------

def test_gate_passes_when_profiles_present_and_fresh(tmp_path: Path) -> None:
    _write_profile(tmp_path, "model-a", updated_at=date.today().isoformat(), authority="official")
    finding = release_checks._check_target_profiles(tmp_path)
    assert finding.status == "pass"


def test_gate_fails_closed_when_profiles_dir_missing(tmp_path: Path) -> None:
    finding = release_checks._check_target_profiles(tmp_path)
    assert finding.status == "fail"
    assert "153" in finding.reason


@pytest.mark.skipif(hasattr(os, "getuid") and os.getuid() == 0,
                     reason="root ignores permission bits")
def test_gate_fails_closed_when_profiles_dir_unreadable(tmp_path: Path) -> None:
    _write_profile(tmp_path, "model-a", updated_at=date.today().isoformat(), authority="official")
    d = tmp_path / "references" / "target-model-profiles"
    d.chmod(0o000)
    try:
        finding = release_checks._check_target_profiles(tmp_path)
    finally:
        d.chmod(0o755)  # restore so tmp_path fixture cleanup can remove it
    assert finding.status == "fail"
    assert "unreadable" in finding.reason


def test_gate_warns_not_fails_on_stale_third_party_profile(tmp_path: Path) -> None:
    stale = (date.today() - timedelta(days=61)).isoformat()
    _write_profile(tmp_path, "model-a", updated_at=stale, authority="third_party")
    finding = release_checks._check_target_profiles(tmp_path)
    assert finding.status == "warn"


def test_gate_fails_on_stale_official_profile(tmp_path: Path) -> None:
    stale = (date.today() - timedelta(days=61)).isoformat()
    _write_profile(tmp_path, "model-a", updated_at=stale, authority="official")
    finding = release_checks._check_target_profiles(tmp_path)
    assert finding.status == "fail"
