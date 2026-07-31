"""Standard-indent JSON codec — deep or irregular structures."""

from __future__ import annotations

import json
from typing import Any

from shiroe.codecs.base import DataShape, ValidationResult, default_token_estimate


class JSONCodec:
    name = "json"
    supported_shapes = (
        DataShape.deep_object,
        DataShape.uniform_records,
        DataShape.typed_output,
    )

    def supports(self, data: object, shape: DataShape) -> bool:
        return shape in self.supported_shapes

    def encode(self, data: Any) -> str:
        return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False)

    def decode(self, payload: str) -> Any:
        return json.loads(payload)

    def validate(self, payload: str) -> ValidationResult:
        try:
            json.loads(payload)
            return ValidationResult(ok=True)
        except json.JSONDecodeError as e:
            return ValidationResult(ok=False, error=str(e))

    def estimate_tokens(self, payload: str, tokenizer: str | None = None) -> int:
        return default_token_estimate(payload)


class CompactJSONCodec(JSONCodec):
    name = "compact_json"

    def encode(self, data: Any) -> str:
        return json.dumps(data, separators=(",", ":"), sort_keys=True, ensure_ascii=False)
