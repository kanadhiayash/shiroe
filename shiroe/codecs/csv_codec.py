"""CSV codec — flat tables and pure record streams."""

from __future__ import annotations

import csv
import io
from typing import Any

from shiroe.codecs.base import DataShape, ValidationResult, default_token_estimate


class CSVCodec:
    name = "csv"
    supported_shapes = (DataShape.flat_table, DataShape.uniform_records)

    def supports(self, data: object, shape: DataShape) -> bool:
        return shape in self.supported_shapes

    def encode(self, data: Any) -> str:
        if not data:
            return ""
        buffer = io.StringIO()
        if isinstance(data[0], dict):
            fieldnames = sorted({k for row in data for k in row})
            writer = csv.DictWriter(buffer, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(data)
        elif isinstance(data[0], (list, tuple)):
            writer = csv.writer(buffer)
            writer.writerows(data)
        else:
            raise ValueError("csv codec expects list-of-dicts or list-of-lists")
        return buffer.getvalue().rstrip("\n")

    def decode(self, payload: str) -> list[dict]:
        reader = csv.DictReader(io.StringIO(payload))
        return list(reader)

    def validate(self, payload: str) -> ValidationResult:
        try:
            list(csv.reader(io.StringIO(payload)))
            return ValidationResult(ok=True)
        except csv.Error as e:
            return ValidationResult(ok=False, error=str(e))

    def estimate_tokens(self, payload: str, tokenizer: str | None = None) -> int:
        return default_token_estimate(payload)
