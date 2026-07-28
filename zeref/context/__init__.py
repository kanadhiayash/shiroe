"""Context packet builder (vNext PR 9, §7.4).

Every model invocation should receive a compiled packet with explicit
sections:

  1. Objective + constraints — markdown
  2. Permission contract     — JSON or markdown+JSON
  3. Relevant memory records — TOON or compact JSON (codec-selected)
  4. Evidence inventory      — TOON or compact JSON
  5. Required output schema  — JSON Schema
  6. Stop / escalation rules — markdown
"""

from zeref.context.allocator import (
    AllocationBudget,
    AllocationResult,
    AllocatorError,
    Omission,
    allocate_packet,
    resolve_capability,
)
from zeref.context.packet import ContextPacket, build_packet

__all__ = [
    "ContextPacket",
    "build_packet",
    "AllocationBudget",
    "AllocationResult",
    "AllocatorError",
    "Omission",
    "allocate_packet",
    "resolve_capability",
]
