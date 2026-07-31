"""vNext PR 17 gate tests — Odysseus adapter."""

from __future__ import annotations

from pathlib import Path

from shiroe.adapters.harnesses.odysseus import OdysseusAdapter


def test_odysseus_context_only_without_signals(monkeypatch) -> None:
    monkeypatch.delenv("ODYSSEUS_VERSION", raising=False)
    monkeypatch.delenv("ODYSSEUS_API_ENDPOINT", raising=False)
    monkeypatch.setattr("shiroe.adapters.harnesses.odysseus.which",
                         lambda cmd: None)
    r = OdysseusAdapter().detect()
    assert not r.detected
    assert r.enforcement_level.value == "C"


def test_odysseus_sidecar_when_api_endpoint_set(monkeypatch) -> None:
    monkeypatch.setenv("ODYSSEUS_API_ENDPOINT", "https://o.example/api")
    monkeypatch.delenv("ODYSSEUS_VERSION", raising=False)
    monkeypatch.setattr("shiroe.adapters.harnesses.odysseus.which",
                         lambda cmd: None)
    r = OdysseusAdapter().detect()
    assert r.detected
    # Odysseus owns its own runtime; Zeref integrates via API.
    assert r.enforcement_level.value == "B"


def test_odysseus_ODYSSEUS_md_notes_licensing_boundary(tmp_path: Path) -> None:
    written = OdysseusAdapter().export_context(
        tmp_path, objective="do the work", permissions={"net": "denied"},
    )
    text = written[0].read_text("utf-8")
    assert "authenticated API" in text
    assert "AGPL" in text
    assert "MIT" in text


def test_odysseus_features() -> None:
    r = OdysseusAdapter().detect()
    for f in ("ODYSSEUS.md", "api_bridge", "plugin_bridge", "MCP"):
        assert f in r.supported_features
