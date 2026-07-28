"""ZRF-66 / issue #172: external benchmark truth gate.

Covers the capability evidence matrix and the three encoded claim-gate
constraints: routing-accuracy fixture-coverage, contested vendor
comparisons + missing baselines, and unscored external benchmarks.
"""

from __future__ import annotations

from pathlib import Path

from zeref.release.claim_gate import (
    build_capability_matrix,
    run_claim_gate,
    scan_public_claims,
)


def test_live_repo_public_docs_pass_clean(repo_root: Path) -> None:
    """The real repo's public surface must currently be clean — this is the
    regression lock: any future doc edit that trips a constraint fails here,
    not silently in production."""
    passed, findings = run_claim_gate(repo_root)
    assert passed, f"unexpected blocked claim(s) in live docs: {findings}"


def test_capability_matrix_blocks_routing_classifier(repo_root: Path) -> None:
    entries = {e.capability: e for e in build_capability_matrix(repo_root)}
    routing = entries["routing_criticality_classifier"]
    assert routing.public_claim_allowed is False
    assert routing.evidence_tier == "fixture_tested"
    assert routing.namespace == "conformance"


def test_capability_matrix_blocks_all_external_benchmarks(repo_root: Path) -> None:
    entries = {e.capability: e for e in build_capability_matrix(repo_root)}
    for name in ("locomo", "longmemeval", "personamem", "ruler", "helmet"):
        entry = entries[f"external_benchmark_{name}"]
        assert entry.public_claim_allowed is False
        assert entry.namespace == "external_benchmark"


def test_capability_matrix_covers_registered_gates(repo_root: Path) -> None:
    entries = build_capability_matrix(repo_root)
    gate_caps = [e for e in entries if e.capability.startswith("gate:")]
    assert len(gate_caps) == 5  # zeref-registry.json currently declares 5 gates
    # every gate in this repo has a matching pytest module, so all are claimable
    assert all(e.public_claim_allowed for e in gate_caps), gate_caps


def test_blocks_critical_recall_claim(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text(
        "Zeref's routing classifier achieves 100% CRITICAL recall.\n",
        encoding="utf-8",
    )
    findings = scan_public_claims(tmp_path)
    assert any(f.constraint == "routing_accuracy_fixture_coverage" for f in findings)


def test_blocks_contested_vendor_comparison(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text(
        "Zeref beats Zep and Mem0 on LoCoMo accuracy.\n",
        encoding="utf-8",
    )
    findings = scan_public_claims(tmp_path)
    assert any(f.constraint == "contested_vendor_comparison" for f in findings)


def test_allows_citing_vendor_baselines_without_zeref_ranking(tmp_path: Path) -> None:
    """Citing a vendor's own published figures for context — e.g. Mem0's
    baseline showing full-context beats Mem0 — is not Zeref making a
    ranking claim, and must not trip the gate just for mentioning a vendor
    name near a comparison word."""
    (tmp_path / "README.md").write_text(
        "Mem0's own baseline: full-context 72.9% vs Mem0 66.9%.\n",
        encoding="utf-8",
    )
    findings = scan_public_claims(tmp_path)
    assert not any(f.constraint == "contested_vendor_comparison" for f in findings)


def test_blocks_zeref_score_without_baselines(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text(
        "Zeref scores 91% on the LoCoMo benchmark.\n",
        encoding="utf-8",
    )
    findings = scan_public_claims(tmp_path)
    assert any(f.constraint == "missing_baseline_pair" for f in findings)


def test_allows_zeref_score_with_both_baselines(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text(
        "Zeref scores 91% on the LoCoMo benchmark, next to a full-context "
        "baseline of 88% and a lexical baseline of 74%.\n",
        encoding="utf-8",
    )
    findings = scan_public_claims(tmp_path)
    assert not any(f.constraint == "missing_baseline_pair" for f in findings)


def test_blocks_unscored_external_benchmark_number(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "results.md").write_text(
        "Our LongMemEval accuracy is 82.3%.\n", encoding="utf-8",
    )
    findings = scan_public_claims(tmp_path)
    assert any(f.constraint == "unscored_external_benchmark" for f in findings)


def test_allows_explicit_unscored_disclaimer(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text(
        "No dataset runs have been performed and no scores exist for LoCoMo.\n",
        encoding="utf-8",
    )
    findings = scan_public_claims(tmp_path)
    assert findings == []


def test_run_claim_gate_reports_pass_and_fail(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("Zeref is a local-first memory layer.\n", encoding="utf-8")
    passed, findings = run_claim_gate(tmp_path)
    assert passed is True
    assert findings == []

    (tmp_path / "README.md").write_text(
        "Zeref beats Mem0 on every axis.\n", encoding="utf-8",
    )
    passed, findings = run_claim_gate(tmp_path)
    assert passed is False
    assert findings
