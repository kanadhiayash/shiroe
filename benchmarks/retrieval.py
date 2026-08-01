"""Retrieval axis — deterministic Memory Core benchmark.

privacy-audit: allow-file "Retrieval scorer references example query patterns + fields; no user data."
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from shiroe.memory import scaffold_project
from shiroe.memory_state import MemoryStore
from benchmarks.adapters import adapter_summary, run_fixture_adapters

REPO = Path(__file__).resolve().parent.parent
FIXTURES = REPO / "benchmarks" / "fixtures" / "retrieval_cases.json"


def _fixture_ids() -> set[str]:
    return {case["id"] for case in json.loads(FIXTURES.read_text(encoding="utf-8"))}


def _store() -> MemoryStore:
    root = Path(tempfile.mkdtemp(prefix="shiroe-retrieval-"))
    (root / "AGENTS.md").write_text("# AGENTS.md\n", encoding="utf-8")
    scaffold_project(root, name="retrieval-benchmark", privacy="abstract", tier="auto", parent="")
    return MemoryStore.from_root(root)


def _continuity() -> tuple[float, str]:
    store = _store()
    item = store.add(
        kind="decision",
        title="recall decision",
        body="Use explainable recall for project continuity.",
        entity="Shiroe",
        layer="L1",
        source_ref="benchmarks/fixtures/retrieval_cases.json#continuity",
        confidence="high",
        authority="canonical",
    )
    results = store.search("continuity recall", entity="Shiroe", limit=3)
    ok = (
        len(results) == 1
        and results[0].id == item.id
        and results[0].source_ref
        and results[0].confidence == "high"
        and results[0].authority == "canonical"
        and results[0].why_returned
    )
    return (10.0 if ok else 0.0, "returns source_ref/confidence/authority/why_returned")


def _privacy_recall() -> tuple[float, str]:
    store = _store()
    raw_secret = "access token demo-credential-value-12345"
    item = store.add(
        kind="risk",
        title="credential exposure",
        body=f"Rotate {raw_secret} before public release.",
        entity="security",
        layer="L0",
        source_ref="privacy-fixture",
        confidence="high",
        authority="confirmed",
    )
    fetched = store.get(item.id)
    raw_results = store.search(raw_secret)
    redacted_results = store.search("REDACTED")
    ok = (
        fetched is not None
        and raw_secret not in fetched.body
        and raw_results == []
        and len(redacted_results) == 1
    )
    return (10.0 if ok else 0.0, "raw credential fixture scrubbed before recall")


def _contradiction() -> tuple[float, str]:
    store = _store()
    store.add(
        kind="assumption",
        title="sync policy off",
        body="External sync is off by default.",
        entity="sync-policy",
        layer="L1",
        source_ref="policy-a",
        confidence="high",
        authority="canonical",
    )
    store.add(
        kind="assumption",
        title="sync policy requested",
        body="User requested Linear and GitHub delivery sync for this project.",
        entity="sync-policy",
        layer="L1",
        source_ref="policy-b",
        confidence="medium",
        authority="confirmed",
    )
    results = store.search("sync policy", entity="sync-policy", kind="assumption", limit=5)
    ok = len(results) == 2 and {r.source_ref for r in results} == {"policy-a", "policy-b"}
    return (10.0 if ok else 0.0, "conflicting same-entity assumptions both returned")


def _freshness() -> tuple[float, str]:
    store = _store()
    item = store.add(
        kind="unknown",
        title="freshness target",
        body="old retrieval body",
        entity="freshness",
        layer="L2",
        source_ref="freshness-fixture",
        confidence="low",
        authority="inferred",
    )
    store.update(item.id, body="new retrieval body", confidence="high", authority="confirmed")
    results = store.search("new retrieval", entity="freshness", limit=1)
    history = store.history(item.id)
    ok = (
        len(results) == 1
        and results[0].body == "new retrieval body"
        and results[0].confidence == "high"
        and history[0].event == "memory-update"
    )
    return (10.0 if ok else 0.0, "updated item is freshest and history records update")


def _abstention() -> tuple[float, str]:
    store = _store()
    store.add(
        kind="decision",
        title="known item",
        body="This memory item should not match unrelated queries.",
        entity="known",
        layer="L3",
        source_ref="abstention-fixture",
        confidence="medium",
        authority="confirmed",
    )
    results = store.search("nonexistent-needle-phrase", limit=5)
    return (10.0 if results == [] else 0.0, "unmatched query returns empty result set")


def run() -> dict:
    expected = {"continuity", "privacy_recall", "contradiction", "freshness", "abstention"}
    fixtures_ok = _fixture_ids() == expected
    adapter_results = run_fixture_adapters()
    adapter_score, adapter_evidence = adapter_summary(adapter_results)
    subs = {
        "fixture_inventory": (10.0 if fixtures_ok else 0.0, f"{len(_fixture_ids())}/5 fixtures present"),
        "continuity": _continuity(),
        "privacy_recall": _privacy_recall(),
        "contradiction": _contradiction(),
        "freshness": _freshness(),
        "abstention": _abstention(),
        "external_adapter_fixtures": (adapter_score, adapter_evidence),
    }
    axis = sum(s for s, _ in subs.values()) / len(subs)
    return {
        "axis": "retrieval",
        "score": round(axis, 2),
        "sub": {k: {"score": round(s, 2), "evidence": e} for k, (s, e) in subs.items()},
        "note": "Deterministic lexical/FTS5 retrieval benchmark; external adapters are fixture-only unless marked verified.",
        "adapters": [result.to_dict() for result in adapter_results],
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
