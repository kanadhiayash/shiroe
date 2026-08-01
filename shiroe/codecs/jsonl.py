"""JSONL codec — one record per line; efficient for uniform record streams."""

from __future__ import annotations

import json
from typing import Any

from shiroe.codecs.base import DataShape, ValidationResult, default_token_estimate


class JSONLCodec:
    name = "jsonl"
    supported_shapes = (DataShape.uniform_records,)

    def supports(self, data: object, shape: DataShape) -> bool:
        return shape is DataShape.uniform_records and isinstance(data, list)

    def encode(self, data: Any) -> str:
        if not isinstance(data, list):
            raise ValueError("jsonl codec requires a list of records")
        return "\n".join(
            json.dumps(row, separators=(",", ":"), sort_keys=True, ensure_ascii=False)
            for row in data
        )

    def decode(self, payload: str) -> list:
        return [json.loads(line) for line in payload.splitlines() if line.strip()]

    def validate(self, payload: str) -> ValidationResult:
        try:
            for line in payload.splitlines():
                if line.strip():
                    json.loads(line)
        except json.JSONDecodeError as e:
            return ValidationResult(ok=False, error=str(e))
        return ValidationResult(ok=True)

    def estimate_tokens(self, payload: str, tokenizer: str | None = None) -> int:
        return default_token_estimate(payload)
