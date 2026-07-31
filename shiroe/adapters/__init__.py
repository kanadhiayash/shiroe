"""Adapter layer (vNext §12).

Everything provider-specific or harness-specific lives under this package.
Core modules and canonical schemas reference reasoning classes
(``shiroe.core.reasoning``) and adapter/provider ids only — never concrete
model names.
"""

from __future__ import annotations

import json
from pathlib import Path

_HARNESS_TARGETS = Path(__file__).parent / "harness_targets.json"
_targets_cache: dict[str, str | None] | None = None


def default_profile_for_target(target: str) -> str | None:
    """Default target-model profile id for a handoff/prompt wrapper target."""
    global _targets_cache
    if _targets_cache is None:
        data = json.loads(_HARNESS_TARGETS.read_text(encoding="utf-8"))
        _targets_cache = data["targets"]
    return _targets_cache.get(target)
