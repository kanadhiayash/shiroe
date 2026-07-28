"""Codec protocol + shared types."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Protocol, runtime_checkable


class CodecError(ValueError):
    pass


class DataShape(str, Enum):
    prose = "prose"                # long-form text, rationale, policies
    uniform_records = "uniform_records"  # list of dicts with same keys
    flat_table = "flat_table"      # 2D matrix, header row
    deep_object = "deep_object"    # nested / irregular
    typed_output = "typed_output"  # schema-driven model output


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    error: str | None = None
    metadata: dict | None = None


@runtime_checkable
class ContextCodec(Protocol):
    name: str
    supported_shapes: tuple[DataShape, ...]

    def supports(self, data: object, shape: DataShape) -> bool: ...
    def encode(self, data: object) -> str: ...
    def decode(self, payload: str) -> object: ...
    def validate(self, payload: str) -> ValidationResult: ...
    def estimate_tokens(self, payload: str,
                        tokenizer: str | None = None) -> int: ...


def infer_shape(data: object) -> DataShape:
    """Best-effort classification for the auto-selector."""
    if isinstance(data, str):
        return DataShape.prose
    if isinstance(data, list) and data and all(isinstance(x, dict) for x in data):
        keys = set(data[0].keys())
        if all(set(x.keys()) == keys for x in data):
            first = data[0]
            if all(not isinstance(v, (dict, list)) for v in first.values()):
                return DataShape.uniform_records
        return DataShape.deep_object
    if isinstance(data, list) and data and all(
        isinstance(x, list) and all(not isinstance(y, (dict, list)) for y in x)
        for x in data
    ):
        return DataShape.flat_table
    return DataShape.deep_object


def default_token_estimate(payload: str) -> int:
    """Conservative, tokenizer-independent estimate. Codecs override this
    when they can produce something better (e.g. a real tokenizer).

    Whitespace-run counting alone (words * 1.33) collapses to ~0 tokens for
    any dense or non-Latin-script text (CJK, Devanagari, Arabic, minified
    JSON/code, base64) since those have few or no ASCII spaces — silently
    undercounting and letting oversized content walk through budget checks.
    Instead this takes the MAX of three independent signals so it
    structurally cannot materially undercount: overcounting is safe,
    undercounting can blow a context window.
    """
    if not payload:
        return 0
    word_count = len(re.findall(r"\S+", payload))
    word_estimate = math.ceil(word_count * 4 / 3)
    char_estimate = math.ceil(len(payload) / 2.5)
    byte_estimate = math.ceil(len(payload.encode("utf-8")) / 3)
    return max(1, word_estimate, char_estimate, byte_estimate)
