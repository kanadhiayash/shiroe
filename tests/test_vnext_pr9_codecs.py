"""vNext PR 9 gate tests — context compiler + codecs."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from shiroe.codecs import (
    CODECS,
    DataShape,
    infer_shape,
    list_codecs,
    resolve_codec,
    select_codec,
)
from shiroe.codecs.csv_codec import CSVCodec
from shiroe.codecs.json_codec import CompactJSONCodec, JSONCodec
from shiroe.codecs.jsonl import JSONLCodec
from shiroe.codecs.markdown import MarkdownCodec
from shiroe.codecs.selector import render
from shiroe.codecs.toon import TOONCodec
from shiroe.context import build_packet
from shiroe.storage import StateDB


# ---------------------------------------------------------------------------
# infer_shape + registry
# ---------------------------------------------------------------------------

def test_infer_shape_prose() -> None:
    assert infer_shape("hello world") is DataShape.prose


def test_infer_shape_uniform_records() -> None:
    data = [{"a": 1, "b": 2}, {"a": 3, "b": 4}]
    assert infer_shape(data) is DataShape.uniform_records


def test_infer_shape_deep_object_when_keys_differ() -> None:
    data = [{"a": 1}, {"a": 1, "b": 2}]
    assert infer_shape(data) is DataShape.deep_object


def test_infer_shape_flat_table() -> None:
    data = [[1, 2, 3], [4, 5, 6]]
    assert infer_shape(data) is DataShape.flat_table


def test_all_codecs_registered_and_listable() -> None:
    names = {c["name"] for c in list_codecs()}
    for expected in ("markdown", "json", "compact_json", "jsonl", "csv", "toon"):
        assert expected in names
    for name in names:
        assert resolve_codec(name) is not None


def test_resolve_unknown_codec_raises() -> None:
    with pytest.raises(KeyError):
        resolve_codec("nothing-like-this")


# ---------------------------------------------------------------------------
# Round-trip
# ---------------------------------------------------------------------------

def test_json_roundtrip() -> None:
    codec = JSONCodec()
    data = {"a": 1, "b": [1, 2, 3], "c": {"nested": True}}
    encoded = codec.encode(data)
    assert codec.decode(encoded) == data


def test_compact_json_shorter_than_json() -> None:
    data = {"a": 1, "b": [1, 2, 3]}
    assert len(CompactJSONCodec().encode(data)) < len(JSONCodec().encode(data))


def test_jsonl_roundtrip() -> None:
    codec = JSONLCodec()
    data = [{"id": 1, "n": "a"}, {"id": 2, "n": "b"}]
    encoded = codec.encode(data)
    assert codec.decode(encoded) == data
    lines = encoded.splitlines()
    assert len(lines) == 2
    assert lines[0].startswith("{") and lines[0].endswith("}")


def test_csv_roundtrip() -> None:
    codec = CSVCodec()
    data = [{"a": "1", "b": "x"}, {"a": "2", "b": "y"}]
    encoded = codec.encode(data)
    decoded = codec.decode(encoded)
    assert decoded == data


def test_toon_roundtrip_preserves_records() -> None:
    codec = TOONCodec()
    data = [{"id": "1", "name": "alpha"}, {"id": "2", "name": "beta"}]
    encoded = codec.encode(data)
    assert "~ records ~" in encoded
    decoded = codec.decode(encoded)
    assert decoded == data


def test_toon_escapes_separator() -> None:
    codec = TOONCodec()
    data = [{"note": "a;b;c"}]
    encoded = codec.encode(data)
    # The separator inside a value must be escaped so the split round-trips.
    assert codec.decode(encoded) == data


def test_markdown_encode_dict_and_list() -> None:
    codec = MarkdownCodec()
    assert "**a**: 1" in codec.encode({"a": 1})
    assert "- one" in codec.encode(["one", "two"])


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def test_json_validate_rejects_garbage() -> None:
    result = JSONCodec().validate("{ not json")
    assert not result.ok
    assert result.error


def test_toon_validate_rejects_missing_header() -> None:
    result = TOONCodec().validate("id;name\n- 1;a\n")
    assert not result.ok


# ---------------------------------------------------------------------------
# Selector
# ---------------------------------------------------------------------------

def test_selector_defaults_by_shape() -> None:
    assert select_codec("hello").codec == "markdown"
    assert select_codec([{"a": 1}, {"a": 2}]).codec == "compact_json"
    assert select_codec([[1, 2], [3, 4]]).codec == "csv"
    assert select_codec({"nested": {"deep": True}}).codec == "compact_json"


def test_selector_benchmark_override(tmp_path: Path) -> None:
    """A ``codec_profiles`` row for a specific model/shape overrides the
    default (§7.5 — TOON becomes default only when it wins benchmarks)."""
    db = StateDB(tmp_path); db.migrate()
    conn = db.connect()
    conn.execute(
        """
        INSERT INTO codec_profiles
            (id, codec, model_or_harness, data_shape,
             tokens, latency_ms, comprehension, parse, reliability,
             recorded_at)
        VALUES (?, 'toon', 'sonnet', 'uniform_records',
                100, 50, 0.9, 1.0, 0.95, '2026-07-12T00:00:00')
        """,
        ("cp_1",),
    )
    conn.commit()

    data = [{"id": 1, "n": "a"}]
    default_choice = select_codec(data)
    assert default_choice.codec == "compact_json"

    override_choice = select_codec(data, model_or_harness="sonnet", conn=conn)
    assert override_choice.codec == "toon"
    assert "benchmark override" in override_choice.reason
    db.close()


def test_render_returns_choice_and_text() -> None:
    text, choice = render([{"a": 1}])
    assert choice.codec == "compact_json"
    assert "a" in text


# ---------------------------------------------------------------------------
# Context packet
# ---------------------------------------------------------------------------

def test_build_packet_sections_present() -> None:
    packet = build_packet(
        objective="Ship the change safely.",
        permissions={"network": "denied", "fs.write": ["project"]},
        memory_records=[{"id": "m1", "kind": "decision", "claim": "use SQLite"}],
        evidence=[{"source": "adr-0001", "grade": "strong"}],
        output_schema={"$schema": "http://json-schema.org/draft-07/schema#",
                       "type": "object"},
        stop_rules="Stop on any policy denial.",
    )
    for section in ("objective", "permissions", "memory", "evidence",
                    "output_schema", "stop_rules"):
        assert section in packet.sections
    assert packet.codec_choices["objective"] == "markdown"
    assert packet.codec_choices["output_schema"] == "json"
    assert "Ship the change safely" in packet.as_text()


def test_build_packet_omits_empty_optional_sections() -> None:
    packet = build_packet(
        objective="Just the plan.",
        permissions={"read": "project"},
    )
    assert "objective" in packet.sections
    assert "permissions" in packet.sections
    for absent in ("memory", "evidence", "output_schema", "stop_rules"):
        assert absent not in packet.sections
