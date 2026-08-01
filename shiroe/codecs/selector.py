"""Codec auto-selector (vNext §7.3).

Deterministic rules that produce sensible defaults; benchmarks (PR 19)
can override per (model_profile, data_shape) tuple through
``codec_profiles`` rows in PR 2's SQLite v2 table.

Default policy:
- prose                → markdown
- uniform_records      → compact_json (safe default); csv or toon only
                         when explicitly requested or benchmark-blessed
- flat_table           → csv
- deep_object          → compact_json
- typed_output         → json (standard-indent for readability)
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from shiroe.codecs.base import DataShape, infer_shape
from shiroe.codecs.registry import resolve_codec


@dataclass(frozen=True)
class CodecChoice:
    codec: str
    reason: str


_DEFAULTS: dict[DataShape, str] = {
    DataShape.prose: "markdown",
    DataShape.uniform_records: "compact_json",
    DataShape.flat_table: "csv",
    DataShape.deep_object: "compact_json",
    DataShape.typed_output: "json",
}


def _benchmark_override(conn: sqlite3.Connection | None,
                       model_or_harness: str | None,
                       shape: DataShape) -> str | None:
    if conn is None or model_or_harness is None:
        return None
    row = conn.execute(
        """
        SELECT codec FROM codec_profiles
        WHERE model_or_harness = ? AND data_shape = ?
        ORDER BY reliability DESC, comprehension DESC, recorded_at DESC
        LIMIT 1
        """,
        (model_or_harness, shape.value),
    ).fetchone()
    return row[0] if row else None


def select_codec(data: object,
                 *,
                 shape: DataShape | None = None,
                 model_or_harness: str | None = None,
                 conn: sqlite3.Connection | None = None) -> CodecChoice:
    resolved_shape = shape or infer_shape(data)
    override = _benchmark_override(conn, model_or_harness, resolved_shape)
    if override:
        return CodecChoice(
            codec=override,
            reason=f"benchmark override for {model_or_harness}/{resolved_shape.value}",
        )
    default = _DEFAULTS[resolved_shape]
    return CodecChoice(
        codec=default,
        reason=f"default for shape {resolved_shape.value}",
    )


def render(data: object,
           *,
           shape: DataShape | None = None,
           model_or_harness: str | None = None,
           conn: sqlite3.Connection | None = None) -> tuple[str, CodecChoice]:
    choice = select_codec(data, shape=shape, model_or_harness=model_or_harness, conn=conn)
    codec = resolve_codec(choice.codec)
    return codec.encode(data), choice
