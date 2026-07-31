"""Context codecs (vNext PR 9, master plan §7).

Codecs translate structured data into a model-facing representation.
TOON is one of several — never canonical. Selection is data-shape +
model-profile driven; benchmark history steers it.

Canonical invariant:

    Codecs are strictly for the *model input* projection.
    They never replace SQLite (canonical state) or JSONL (canonical
    history).
"""

from shiroe.codecs.base import (
    CodecError,
    ContextCodec,
    DataShape,
    ValidationResult,
    infer_shape,
)
from shiroe.codecs.registry import CODECS, list_codecs, resolve_codec
from shiroe.codecs.selector import select_codec

__all__ = [
    "CodecError", "ContextCodec", "DataShape", "ValidationResult",
    "infer_shape",
    "CODECS", "list_codecs", "resolve_codec",
    "select_codec",
]
