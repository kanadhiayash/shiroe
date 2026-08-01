"""vNext PR 18 gate tests — Grok provider / context adapter."""

from __future__ import annotations

from pathlib import Path

from shiroe.adapters.providers.xai import GrokContextAdapter


def test_grok_context_only_without_api_key(monkeypatch) -> None:
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    monkeypatch.delenv("GROK_API_KEY", raising=False)
    r = GrokContextAdapter().detect()
    assert not r.detected
    assert r.enforcement_level.value == "C"


def test_grok_detected_but_still_context_only_with_key(monkeypatch) -> None:
    """Grok is a PROVIDER — even when detected the runtime enforcement
    stays at C. No claim of full harness support (§12.2 Grok gate)."""
    monkeypatch.setenv("XAI_API_KEY", "xai-abcd")
    r = GrokContextAdapter().detect()
    assert r.detected
    # This is the acceptance-gate assertion.
    assert r.enforcement_level.value == "C"


def test_grok_GROK_md_states_no_runtime_enforcement(tmp_path: Path) -> None:
    written = GrokContextAdapter().export_context(
        tmp_path, objective="ship it", permissions={"net": "denied"},
    )
    text = written[0].read_text("utf-8")
    assert "PROVIDER" in text
    assert "no runtime enforcement is claimed" in text


def test_grok_features() -> None:
    r = GrokContextAdapter().detect()
    for f in ("GROK.md", "provider_api", "context_projection"):
        assert f in r.supported_features
