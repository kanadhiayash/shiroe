"""Benchmark artifact schema + validator (§16.10)."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


ARTIFACT_SCHEMA = "shiroe.benchmark-artifact/v1"

_REQUIRED = (
    "schema", "id", "category", "name", "shiroe_version", "shiroe_commit",
    "harness", "harness_version", "model_or_provider",
    "dataset_version", "configuration", "seed", "runs",
    "mean", "variance", "failures", "abstentions",
    "raw_artifact_hash", "classification",
)

_ALLOWED_CLASSIFICATIONS = {"fixture", "external", "comparative"}


class ArtifactValidationError(ValueError):
    pass


@dataclass
class BenchmarkArtifact:
    id: str
    category: str
    name: str
    shiroe_version: str
    shiroe_commit: str
    harness: str
    harness_version: str
    model_or_provider: str
    dataset_version: str
    configuration: dict
    seed: int | None
    runs: int
    mean: float
    variance: float
    failures: int
    abstentions: int
    raw_artifact_hash: str
    classification: str
    schema: str = ARTIFACT_SCHEMA
    known_limitations: list[str] = field(default_factory=list)
    recorded_at: str = ""

    def to_dict(self) -> dict:
        d = self.__dict__.copy()
        return d


def validate_artifact(data: dict) -> None:
    if data.get("schema") != ARTIFACT_SCHEMA:
        raise ArtifactValidationError(
            f"expected schema {ARTIFACT_SCHEMA!r}, got {data.get('schema')!r}"
        )
    for k in _REQUIRED:
        if k not in data:
            raise ArtifactValidationError(f"missing field {k!r}")
    if data["classification"] not in _ALLOWED_CLASSIFICATIONS:
        raise ArtifactValidationError(
            f"classification must be one of {_ALLOWED_CLASSIFICATIONS}; "
            f"got {data['classification']!r}"
        )
    if not str(data["raw_artifact_hash"]).startswith("sha256:"):
        raise ArtifactValidationError(
            "raw_artifact_hash must be sha256-prefixed"
        )
    if data["runs"] < 1:
        raise ArtifactValidationError("runs must be >= 1")


def write_artifact(root: Path | str,
                    artifact: BenchmarkArtifact) -> Path:
    """Persist a validated artifact under
    ``<root>/benchmarks/artifacts/<timestamp>-<id>.json``."""
    root = Path(root)
    out_dir = root / "benchmarks" / "artifacts"
    out_dir.mkdir(parents=True, exist_ok=True)
    if not artifact.recorded_at:
        artifact.recorded_at = datetime.now(timezone.utc).isoformat(
            timespec="seconds"
        )
    payload = artifact.to_dict()
    validate_artifact(payload)
    fname = f"{artifact.recorded_at.replace(':','')}-{artifact.id}.json"
    target = out_dir / fname
    target.write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
    )
    return target


def new_id() -> str:
    return "bench_" + uuid.uuid4().hex[:16]


def sha256_of(data: bytes | str) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return "sha256:" + hashlib.sha256(data).hexdigest()
