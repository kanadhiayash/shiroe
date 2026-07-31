"""Fixture-first memory benchmark adapters.

These adapters model the local shape needed to support external benchmark
datasets without downloading those datasets in default tests.
"""

from __future__ import annotations

import json
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

from shiroe.memory import scaffold_project
from shiroe.memory_state import MemoryStore

REPO = Path(__file__).resolve().parent.parent
FIXTURES = REPO / "benchmarks" / "fixtures" / "adapter_cases.json"

ADAPTERS = {
    "locomo": "LoCoMo",
    "longmemeval": "LongMemEval",
    "beam": "BEAM",
    "personamem": "PersonaMem",
    "personamem_v2": "PersonaMem-v2",
}


@dataclass(frozen=True)
class AdapterResult:
    adapter: str
    status: str
    source: str
    evidence: str

    def to_dict(self) -> dict:
        return asdict(self)


def run_fixture_adapters() -> list[AdapterResult]:
    if not FIXTURES.exists():
        return [
            AdapterResult(adapter=name, status="not_configured", source="", evidence="adapter fixture file missing")
            for name in ADAPTERS.values()
        ]
    fixtures = json.loads(FIXTURES.read_text(encoding="utf-8"))
    return [_run_one(key, label, fixtures.get(key)) for key, label in ADAPTERS.items()]


def adapter_summary(results: list[AdapterResult]) -> tuple[float, str]:
    if not results:
        return 0.0, "no adapter results"
    fixture_pass = sum(1 for result in results if result.status == "fixture_pass")
    score = 10.0 if fixture_pass == len(results) else round(10.0 * fixture_pass / len(results), 2)
    statuses = ", ".join(f"{result.adapter}={result.status}" for result in results)
    return score, statuses


def results_json() -> str:
    return json.dumps([result.to_dict() for result in run_fixture_adapters()], indent=2, sort_keys=True) + "\n"


def _run_one(key: str, label: str, fixture: dict | None) -> AdapterResult:
    if not fixture:
        return AdapterResult(adapter=label, status="not_configured", source="", evidence="fixture missing")
    store = _store(key)
    item = store.add(
        kind="source_claim",
        title=f"{label} fixture",
        body=fixture["memory"],
        entity=key,
        layer="L2",
        source_ref=fixture["source"],
        confidence="medium",
        authority="confirmed",
    )
    results = store.search(fixture["query"], entity=key, limit=3)
    haystack = " ".join(result.body.lower() for result in results)
    expected = [term.lower() for term in fixture.get("expected_terms", [])]
    passed = results and results[0].id == item.id and all(term in haystack for term in expected)
    return AdapterResult(
        adapter=label,
        status="fixture_pass" if passed else "full_dataset_pending",
        source=fixture["source"],
        evidence="offline fixture pass; full external dataset not downloaded by default" if passed else "fixture did not pass",
    )


def _store(name: str) -> MemoryStore:
    root = Path(tempfile.mkdtemp(prefix=f"zeref-{name}-adapter-"))
    (root / "AGENTS.md").write_text("# AGENTS.md\n", encoding="utf-8")
    scaffold_project(root, name=f"{name}-adapter", privacy="abstract", tier="auto", parent="")
    return MemoryStore.from_root(root)


if __name__ == "__main__":
    print(results_json(), end="")
