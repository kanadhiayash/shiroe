"""External benchmark program (vNext PR 19, master plan §16).

Every benchmark artifact carries the §16.10 provenance envelope:
Shiroe version + commit, harness + version, model/provider, dataset
version, configuration, seed, run count, mean + variance, failures /
abstentions, raw artifact hashes, and a fixture / external /
comparative label. Nothing else is accepted as a "report".

Categories implemented:
- Deterministic conformance    (§16.1)
- External memory benchmarks   (§16.2, fixture-labeled here)
- Agentic-operation benchmarks (§16.3)
- Capability resolver benchmarks (§16.4)
- Team execution benchmarks    (§16.5)
- Adapter benchmarks           (§16.6)
- Codec benchmarks             (§16.7)
- Evidence / evaluator benchmarks (§16.8)
- Security benchmarks          (§16.9)
"""

from shiroe.benchmark.program.artifact import (
    BenchmarkArtifact,
    ArtifactValidationError,
    validate_artifact,
    write_artifact,
)
from shiroe.benchmark.program.registry import (
    BenchmarkCategory,
    BenchmarkResult,
    Classification,
    list_benchmarks,
    run_benchmark,
)

__all__ = [
    "BenchmarkArtifact", "ArtifactValidationError",
    "validate_artifact", "write_artifact",
    "BenchmarkCategory", "BenchmarkResult", "Classification",
    "list_benchmarks", "run_benchmark",
]
