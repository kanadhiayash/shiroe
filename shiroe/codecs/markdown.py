"""Markdown codec — humans + narrative model input."""

from __future__ import annotations

from typing import Any

from shiroe.codecs.base import DataShape, ValidationResult, default_token_estimate


class MarkdownCodec:
    name = "markdown"
    supported_shapes = (DataShape.prose,)

    def supports(self, data: object, shape: DataShape) -> bool:
        return shape is DataShape.prose

    def encode(self, data: Any) -> str:
        if isinstance(data, str):
            return data
        if isinstance(data, list):
            return "\n".join(f"- {item}" for item in data)
        if isinstance(data, dict):
            return "\n".join(f"**{k}**: {v}" for k, v in data.items())
        return str(data)

    def decode(self, payload: str) -> str:
        return payload

    def validate(self, payload: str) -> ValidationResult:
        return ValidationResult(ok=True)

    def estimate_tokens(self, payload: str, tokenizer: str | None = None) -> int:
        return default_token_estimate(payload)
