"""Codec registry."""

from __future__ import annotations

from shiroe.codecs.base import ContextCodec
from shiroe.codecs.csv_codec import CSVCodec
from shiroe.codecs.json_codec import CompactJSONCodec, JSONCodec
from shiroe.codecs.jsonl import JSONLCodec
from shiroe.codecs.markdown import MarkdownCodec
from shiroe.codecs.toon import TOONCodec


CODECS: dict[str, ContextCodec] = {
    "markdown": MarkdownCodec(),
    "json": JSONCodec(),
    "compact_json": CompactJSONCodec(),
    "jsonl": JSONLCodec(),
    "csv": CSVCodec(),
    "toon": TOONCodec(),
}


def resolve_codec(name: str) -> ContextCodec:
    if name not in CODECS:
        raise KeyError(f"unknown codec {name!r}; known: {sorted(CODECS)}")
    return CODECS[name]


def list_codecs() -> list[dict]:
    return [
        {"name": c.name,
         "supported_shapes": [s.value for s in c.supported_shapes]}
        for c in CODECS.values()
    ]
