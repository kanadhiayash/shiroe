"""vNext PR 16 gate tests — Hermes adapter."""

from __future__ import annotations

from pathlib import Path

from shiroe.adapters.harnesses.hermes import HermesAdapter


def test_hermes_sidecar_when_detected(monkeypatch) -> None:
    monkeypatch.setenv("HERMES_VERSION", "2.0")
    monkeypatch.setattr("shiroe.adapters.harnesses.hermes.which",
                         lambda cmd: None)
    r = HermesAdapter().detect()
    assert r.detected
    # Hermes has its own runtime; Zeref is a sidecar (Level B).
    assert r.enforcement_level.value == "B"


def test_hermes_context_only_when_absent(monkeypatch) -> None:
    monkeypatch.delenv("HERMES_VERSION", raising=False)
    monkeypatch.setattr("shiroe.adapters.harnesses.hermes.which",
                         lambda cmd: None)
    r = HermesAdapter().detect()
    assert not r.detected
    assert r.enforcement_level.value == "C"


def test_hermes_HERMES_md_records_ownership_boundary(tmp_path: Path) -> None:
    written = HermesAdapter().export_context(
        tmp_path, objective="Ship the release.",
        permissions={"net": "denied"},
    )
    text = written[0].read_text("utf-8")
    assert "Ownership" in text
    assert "read-through cache" in text
    assert "Direct writes to Hermes memory are NOT permitted" in text


def test_hermes_features_include_read_through_memory() -> None:
    r = HermesAdapter().detect()
    assert "read_through_memory" in r.supported_features
    assert "skill_proposals" in r.supported_features
