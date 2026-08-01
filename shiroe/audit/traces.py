"""Small helpers for audit-trace payloads."""

from __future__ import annotations


def write_trace(*, guards_run: list[str], source: str, memory_id: str | None = None) -> dict:
    return {"guards_run": guards_run, "source": source, "memory_id": memory_id}
