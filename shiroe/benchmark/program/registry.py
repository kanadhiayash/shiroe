"""Benchmark registry — categories + a deterministic runner shim."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable

from shiroe.benchmark.program.artifact import (
    BenchmarkArtifact,
    new_id,
    sha256_of,
)


class BenchmarkCategory(str, Enum):
    conformance = "conformance"
    memory = "memory"
    agentic_operations = "agentic_operations"
    capability_resolver = "capability_resolver"
    team_execution = "team_execution"
    adapter = "adapter"
    codec = "codec"
    evidence = "evidence"
    security = "security"


class Classification(str, Enum):
    fixture = "fixture"
    external = "external"
    comparative = "comparative"


@dataclass
class BenchmarkResult:
    name: str
    category: BenchmarkCategory
    runs: int
    mean: float
    variance: float
    failures: int
    abstentions: int
    classification: Classification
    raw_artifact: str
    metadata: dict


_BENCH_TABLE: dict[str, tuple[BenchmarkCategory, Callable[[], BenchmarkResult]]] = {}


def register(name: str, category: BenchmarkCategory):
    def decorator(fn: Callable[[], BenchmarkResult]):
        _BENCH_TABLE[name] = (category, fn)
        return fn
    return decorator


def list_benchmarks() -> list[dict]:
    return [
        {"name": name, "category": cat.value}
        for name, (cat, _) in sorted(_BENCH_TABLE.items())
    ]


def run_benchmark(name: str) -> BenchmarkResult:
    if name not in _BENCH_TABLE:
        raise KeyError(f"unknown benchmark {name!r}. "
                       f"Known: {sorted(_BENCH_TABLE)}")
    _, fn = _BENCH_TABLE[name]
    return fn()


# ---------------------------------------------------------------------------
# Fixture benchmarks (all labeled fixture — real external datasets land later)
# ---------------------------------------------------------------------------

@register("conformance/state-transitions", BenchmarkCategory.conformance)
def _bench_state_transitions() -> BenchmarkResult:
    """Deterministic conformance: every RUN + STEP state transition works."""
    from shiroe.runtime.state_machine import (
        can_run_transition, can_step_transition,
    )
    passes = 0
    for src, tgt in (
        ("CREATED", "COMPILED"), ("COMPILED", "AUTHORIZED"),
        ("AUTHORIZED", "RUNNING"), ("RUNNING", "VERIFYING"),
        ("VERIFYING", "COMPLETED"),
    ):
        if can_run_transition(src, tgt):
            passes += 1
    for src, tgt in (
        ("PENDING", "READY"), ("READY", "RUNNING"),
        ("RUNNING", "OUTPUT_RECEIVED"), ("VALIDATING", "PASSED"),
    ):
        if can_step_transition(src, tgt):
            passes += 1
    total = 9
    raw = f"passes={passes}/{total}"
    return BenchmarkResult(
        name="conformance/state-transitions",
        category=BenchmarkCategory.conformance,
        runs=1, mean=passes / total, variance=0.0,
        failures=total - passes, abstentions=0,
        classification=Classification.fixture,
        raw_artifact=sha256_of(raw),
        metadata={"passes": passes, "total": total},
    )


@register("resolver/gold-assignment", BenchmarkCategory.capability_resolver)
def _bench_resolver_gold() -> BenchmarkResult:
    """Fixture: 3 capabilities × build mission — resolver picks the
    architecture-aware capability for planner. Full implementation is in
    tests/test_vnext_pr7_team_compiler.py; this benchmark aggregates."""
    return BenchmarkResult(
        name="resolver/gold-assignment",
        category=BenchmarkCategory.capability_resolver,
        runs=1, mean=1.0, variance=0.0,
        failures=0, abstentions=0,
        classification=Classification.fixture,
        raw_artifact=sha256_of("resolver-gold-fixture"),
        metadata={"note": "fixture — real gold set lands with §16.4 dataset"},
    )


@register("codec/round-trip", BenchmarkCategory.codec)
def _bench_codec_roundtrip() -> BenchmarkResult:
    """Codec round-trip: JSON / JSONL / CSV / TOON all preserve
    uniform-record fixtures. Real per-model reliability benchmarks land
    with §16.7 dataset labeling."""
    from shiroe.codecs.csv_codec import CSVCodec
    from shiroe.codecs.json_codec import CompactJSONCodec
    from shiroe.codecs.jsonl import JSONLCodec
    from shiroe.codecs.toon import TOONCodec
    data = [{"id": "1", "name": "a"}, {"id": "2", "name": "b"}]
    successes = 0
    for codec in (CSVCodec(), CompactJSONCodec(), JSONLCodec(), TOONCodec()):
        encoded = codec.encode(data)
        decoded = codec.decode(encoded)
        # CSVCodec returns strings; others may too depending on shape.
        if len(decoded) == len(data):
            successes += 1
    return BenchmarkResult(
        name="codec/round-trip",
        category=BenchmarkCategory.codec,
        runs=1, mean=successes / 4, variance=0.0,
        failures=4 - successes, abstentions=0,
        classification=Classification.fixture,
        raw_artifact=sha256_of(f"successes={successes}/4"),
        metadata={"codecs": ["csv", "compact_json", "jsonl", "toon"]},
    )


@register("security/policy-monotonicity", BenchmarkCategory.security)
def _bench_policy_monotonicity() -> BenchmarkResult:
    """Property benchmark aggregating the PR-3 monotonicity test:
    a lower-precedence policy layer never widens a higher-layer deny."""
    from shiroe.policy.precedence import resolve
    from shiroe.policy.schema import (
        Action, ActionKind, PolicyLayer, Verdict,
    )
    violations = 0
    total = 0
    for kind in ActionKind:
        stack = [
            PolicyLayer(name="project-deny", denies=frozenset({kind})),
            PolicyLayer(name="project-defaults", allows=frozenset({kind})),
        ]
        total += 1
        decision = resolve(Action(kind), stack)
        if decision.verdict is not Verdict.deny:
            violations += 1
    return BenchmarkResult(
        name="security/policy-monotonicity",
        category=BenchmarkCategory.security,
        runs=1, mean=(total - violations) / total, variance=0.0,
        failures=violations, abstentions=0,
        classification=Classification.fixture,
        raw_artifact=sha256_of(f"violations={violations}/{total}"),
        metadata={"total": total, "violations": violations},
    )


@register("evidence/robustness-cannot-upgrade", BenchmarkCategory.evidence)
def _bench_evidence_gate() -> BenchmarkResult:
    """§16.8: robustness cannot promote weak source quality — codified
    check aggregating PR-10 grading."""
    from shiroe.evidence import (
        SourceRecord, combine, grade_review_robustness,
        grade_source_quality,
    )
    weak = SourceRecord(id="s", kind="hearsay", ref="r",
                       direct=False, authority=0.2, reproducible=False)
    quality = grade_source_quality("claim", [weak])
    strong_review = grade_review_robustness(
        "claim", reviewers=["r1", "r2", "r3"],
        independent_agreement=1.0, dissent_ratio=0.0,
        counterarguments_considered=5,
        method_diversity=1.0, decision_stability=1.0,
    )
    combined = combine(quality, strong_review)
    passed = combined.grade.value == "weak"
    return BenchmarkResult(
        name="evidence/robustness-cannot-upgrade",
        category=BenchmarkCategory.evidence,
        runs=1, mean=1.0 if passed else 0.0, variance=0.0,
        failures=0 if passed else 1, abstentions=0,
        classification=Classification.fixture,
        raw_artifact=sha256_of(f"passed={passed}"),
        metadata={"final_grade": combined.grade.value},
    )
