"""FactGuard claim safety tests."""

from __future__ import annotations

from pathlib import Path

from shiroe.guards.fact_guard import check_claim, classify_claim, scan_path, suggest_rewrite


def test_unsupported_superlative_detection() -> None:
    findings = check_claim("Shiroe is the best AI tactician.")
    assert findings
    assert findings[0].category == "unsupported_superlative"


def test_benchmark_and_production_claim_detection() -> None:
    benchmark = check_claim("Shiroe scores 10/10 on all benchmarks.")
    production = check_claim("Shiroe is production-ready.")
    assert benchmark[0].category == "benchmark_claim"
    assert production[0].category == "production_ready"


def test_source_ref_requirement_for_factual_claims() -> None:
    findings = check_claim("Shiroe supports guarded writes.")
    assert findings[0].category == "missing_source_ref"
    assert check_claim("Shiroe supports guarded writes.", source_refs=["README.md"]) == []


def test_safe_rewrite_suggestion() -> None:
    assert "local-first memory hardening layer" in suggest_rewrite("Shiroe beats every memory tool.")


def test_markdown_scan_output(tmp_path: Path) -> None:
    doc = tmp_path / "README.md"
    doc.write_text("# Demo\n\nShiroe is production-proven.\n", encoding="utf-8")
    findings = scan_path(tmp_path)
    assert len(findings) == 1
    assert findings[0].path.endswith("README.md")


def test_claim_classification() -> None:
    assert classify_claim("Maybe this works.") == "assumption"
    assert classify_claim("Unsupported claim.") == "unsupported_claim"
    assert classify_claim("Shiroe has docs.", source_refs=["README.md"]) == "verified_fact"
