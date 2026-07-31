"""Deterministic 6-section context packet."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from typing import Any

from shiroe.codecs.base import DataShape
from shiroe.codecs.selector import render as codec_render


@dataclass
class ContextPacket:
    objective: str
    permissions: dict
    memory_records: list[dict] = field(default_factory=list)
    evidence: list[dict] = field(default_factory=list)
    output_schema: dict = field(default_factory=dict)
    stop_rules: str = ""
    sections: dict[str, str] = field(default_factory=dict)
    codec_choices: dict[str, str] = field(default_factory=dict)

    def as_text(self) -> str:
        order = ("objective", "permissions", "memory", "evidence",
                 "output_schema", "stop_rules")
        return "\n\n".join(f"## {name}\n{self.sections[name]}"
                           for name in order if name in self.sections)


def build_packet(
    *,
    objective: str,
    permissions: dict,
    memory_records: list[dict] | None = None,
    evidence: list[dict] | None = None,
    output_schema: dict | None = None,
    stop_rules: str = "",
    model_or_harness: str | None = None,
    conn: sqlite3.Connection | None = None,
) -> ContextPacket:
    memory_records = memory_records or []
    evidence = evidence or []
    output_schema = output_schema or {}

    packet = ContextPacket(
        objective=objective, permissions=permissions,
        memory_records=memory_records, evidence=evidence,
        output_schema=output_schema, stop_rules=stop_rules,
    )

    # Section 1 — objective (markdown)
    obj_text, obj_choice = codec_render(
        objective, shape=DataShape.prose,
        model_or_harness=model_or_harness, conn=conn,
    )
    packet.sections["objective"] = obj_text
    packet.codec_choices["objective"] = obj_choice.codec

    # Section 2 — permissions (JSON)
    perm_text, perm_choice = codec_render(
        permissions, shape=DataShape.deep_object,
        model_or_harness=model_or_harness, conn=conn,
    )
    packet.sections["permissions"] = perm_text
    packet.codec_choices["permissions"] = perm_choice.codec

    # Section 3 — memory records (auto-select)
    if memory_records:
        mem_text, mem_choice = codec_render(
            memory_records, shape=DataShape.uniform_records,
            model_or_harness=model_or_harness, conn=conn,
        )
        packet.sections["memory"] = mem_text
        packet.codec_choices["memory"] = mem_choice.codec

    # Section 4 — evidence (auto-select)
    if evidence:
        ev_text, ev_choice = codec_render(
            evidence, shape=DataShape.uniform_records,
            model_or_harness=model_or_harness, conn=conn,
        )
        packet.sections["evidence"] = ev_text
        packet.codec_choices["evidence"] = ev_choice.codec

    # Section 5 — output schema (JSON)
    if output_schema:
        os_text, os_choice = codec_render(
            output_schema, shape=DataShape.typed_output,
            model_or_harness=model_or_harness, conn=conn,
        )
        packet.sections["output_schema"] = os_text
        packet.codec_choices["output_schema"] = os_choice.codec

    # Section 6 — stop rules (markdown)
    if stop_rules:
        packet.sections["stop_rules"] = stop_rules
        packet.codec_choices["stop_rules"] = "markdown"

    return packet
