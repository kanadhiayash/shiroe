"""TOON codec (experimental, vNext §7).

TOON = Token-Optimized Object Notation. A minimal, whitespace-sensitive
representation intended to shave tokens off uniform-record lists relative
to compact JSON. Implementation is a deliberate small subset — never
canonical — used only where the codec selector says a specific model
profile has passed accuracy + reliability benchmarks (PR 19).

Format (v0):

    ~ records ~
    id;name;value
    - 1;alpha;1.5
    - 2;beta;2.0

Escaping: `;` inside a cell becomes `\\;`; leading/trailing whitespace is
preserved via a single leading `.` sentinel when needed.
"""

from __future__ import annotations

from typing import Any

from shiroe.codecs.base import DataShape, ValidationResult, default_token_estimate


SEPARATOR = ";"
_RECORD_HEADER = "~ records ~"
_ESCAPE = "\\"


class TOONCodec:
    name = "toon"
    supported_shapes = (DataShape.uniform_records,)

    def supports(self, data: object, shape: DataShape) -> bool:
        if shape is not DataShape.uniform_records:
            return False
        if not isinstance(data, list) or not data:
            return False
        return all(isinstance(x, dict) for x in data)

    def encode(self, data: Any) -> str:
        if not data:
            return _RECORD_HEADER + "\n"
        keys = sorted({k for row in data for k in row})
        lines = [_RECORD_HEADER, SEPARATOR.join(keys)]
        for row in data:
            cells = []
            for key in keys:
                v = row.get(key, "")
                cells.append(_escape(str(v)))
            lines.append("- " + SEPARATOR.join(cells))
        return "\n".join(lines)

    def decode(self, payload: str) -> list[dict]:
        lines = [l for l in payload.splitlines() if l.strip()]
        if not lines or lines[0].strip() != _RECORD_HEADER:
            raise ValueError("not a TOON payload")
        keys = _split(lines[1])
        out: list[dict] = []
        for line in lines[2:]:
            if not line.startswith("- "):
                continue
            cells = _split(line[2:])
            row = {k: _unescape(v) for k, v in zip(keys, cells)}
            out.append(row)
        return out

    def validate(self, payload: str) -> ValidationResult:
        try:
            self.decode(payload)
            return ValidationResult(ok=True)
        except ValueError as e:
            return ValidationResult(ok=False, error=str(e))

    def estimate_tokens(self, payload: str, tokenizer: str | None = None) -> int:
        return default_token_estimate(payload)


def _escape(s: str) -> str:
    return s.replace(_ESCAPE, _ESCAPE + _ESCAPE).replace(SEPARATOR, _ESCAPE + SEPARATOR)


def _unescape(s: str) -> str:
    return s.replace(_ESCAPE + SEPARATOR, SEPARATOR).replace(_ESCAPE + _ESCAPE, _ESCAPE)


def _split(row: str) -> list[str]:
    out: list[str] = []
    buf = ""
    i = 0
    while i < len(row):
        ch = row[i]
        if ch == _ESCAPE and i + 1 < len(row):
            buf += row[i + 1]
            i += 2
            continue
        if ch == SEPARATOR:
            out.append(buf)
            buf = ""
            i += 1
            continue
        buf += ch
        i += 1
    out.append(buf)
    return out
