"""Provider adapter contract.

A provider adapter maps provider-neutral reasoning classes
(``shiroe.core.reasoning``) to concrete model identifiers. Mapping data is
declarative JSON shipped next to this module — one file per provider.

Two schema versions are accepted:

``shiroe.provider/v1`` (legacy, still loadable)
    .. code-block:: json

        {
          "schema": "shiroe.provider/v1",
          "provider": "anthropic",
          "classes": {
            "frontier": {"model_id": "...", "effort": "high",
                          "restrict_to_criticality": "CRITICAL"}
          }
        }

    v1 entries carry no verification metadata, so every v1 model is treated
    as **unverified** (see ``ModelCapability``) — it fails closed on any
    live-call resolution.

``shiroe.provider/v2`` (current)
    Adds a per-model capability block recording lifecycle, provenance, and
    limits (SHR-60):

    .. code-block:: json

        {
          "schema": "shiroe.provider/v2",
          "provider": "anthropic",
          "classes": {
            "frontier": {
              "model_id": "...", "effort": "high",
              "restrict_to_criticality": "CRITICAL",
              "lifecycle": "active",
              "source_url": "https://docs.example/...",
              "verified_at": "2026-07-27",
              "verified_by": "human",
              "context_window": 1000000,
              "max_output_tokens": 128000,
              "endpoint": "messages",
              "modalities": ["text", "image"],
              "supports_tools": true,
              "supports_structured_output": true,
              "region": "global",
              "retention_class": "standard",
              "fallback": {
                "model_id": "...", "lifecycle": "active",
                "verified_at": "2026-07-27", "verified_by": "human",
                "source_url": "https://docs.example/..."
              }
            }
          }
        }

``restrict_to_criticality`` is advisory metadata mirrored from core policy;
enforcement happens in :func:`shiroe.core.reasoning.validate_request`.

Fail-closed rule (SHR-60): a model resolves on a **live** call only if its
lifecycle is ``"active"`` *and* it is verified (``verified_at`` +
``verified_by`` both present). Anything else — ``deprecated``, ``retired``,
``unknown``, or simply unverified — raises on a live call. Non-live
(``dry_run``) calls may still proceed, carrying a recorded warning, because
nothing is sent anywhere on that path.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from shiroe.core.reasoning import ModelSpec, ReasoningPolicyError, is_reasoning_class

PROVIDER_SCHEMA_V1 = "shiroe.provider/v1"
PROVIDER_SCHEMA_V2 = "shiroe.provider/v2"
SUPPORTED_SCHEMAS = (PROVIDER_SCHEMA_V1, PROVIDER_SCHEMA_V2)
PROVIDER_SCHEMA = PROVIDER_SCHEMA_V2  # kept for callers that want "the current schema"

LIFECYCLE_STATES: tuple[str, ...] = ("active", "deprecated", "retired", "unknown")
VERIFIED_BY_VALUES: tuple[str, ...] = ("human", "api")


class ProviderAdapter(Protocol):
    provider: str

    def resolve(self, reasoning_class: str, *, live: bool = True) -> ModelSpec: ...

    def supported_classes(self) -> tuple[str, ...]: ...


@dataclass(frozen=True)
class ModelCapability:
    """Verification + limits record for one concrete model (SHR-60).

    ``verified`` is derived, never stored directly: a model is verified only
    when both ``verified_at`` and ``verified_by`` were actually recorded.
    That is the guard against the failure this ticket exists to fix — a
    fabricated verification is worse than an honest "unverified".
    """

    lifecycle: str = "unknown"
    source_url: str | None = None
    verified_at: str | None = None
    verified_by: str | None = None
    context_window: int | None = None
    max_output_tokens: int | None = None
    endpoint: str | None = None
    modalities: tuple[str, ...] = ()
    supports_tools: bool | None = None
    supports_structured_output: bool | None = None
    region: str | None = None
    retention_class: str | None = None

    @property
    def verified(self) -> bool:
        return self.verified_at is not None and self.verified_by is not None

    def fails_closed(self) -> bool:
        """True if a live call must be refused for this model."""
        return self.lifecycle != "active" or not self.verified


def _parse_capability(entry: dict, *, schema: str) -> ModelCapability:
    """Build a :class:`ModelCapability` from one class (or fallback) entry.

    v1 entries have none of these keys, so every field falls back to its
    "unverified" default — that is the point, not an oversight.
    """
    if schema == PROVIDER_SCHEMA_V1:
        return ModelCapability()

    lifecycle = entry.get("lifecycle", "unknown")
    if lifecycle not in LIFECYCLE_STATES:
        raise ValueError(
            f"unknown lifecycle {lifecycle!r}; expected one of {LIFECYCLE_STATES}"
        )
    verified_by = entry.get("verified_by")
    if verified_by is not None and verified_by not in VERIFIED_BY_VALUES:
        raise ValueError(
            f"unknown verified_by {verified_by!r}; expected one of {VERIFIED_BY_VALUES}"
        )
    modalities = entry.get("modalities", ())
    return ModelCapability(
        lifecycle=lifecycle,
        source_url=entry.get("source_url"),
        verified_at=entry.get("verified_at"),
        verified_by=verified_by,
        context_window=entry.get("context_window"),
        max_output_tokens=entry.get("max_output_tokens"),
        endpoint=entry.get("endpoint"),
        modalities=tuple(modalities),
        supports_tools=entry.get("supports_tools"),
        supports_structured_output=entry.get("supports_structured_output"),
        region=entry.get("region"),
        retention_class=entry.get("retention_class"),
    )


class JsonProviderAdapter:
    """Provider adapter backed by a declarative JSON mapping file."""

    def __init__(self, path: Path):
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        schema = data.get("schema")
        if schema not in SUPPORTED_SCHEMAS:
            raise ValueError(
                f"{path}: expected schema one of {SUPPORTED_SCHEMAS!r}, got {schema!r}"
            )
        self.schema: str = schema
        self.provider: str = data["provider"]
        self._classes: dict[str, dict] = data["classes"]
        for cls, entry in self._classes.items():
            if not is_reasoning_class(cls):
                raise ValueError(f"{path}: unknown reasoning class {cls!r}")
            # Validate eagerly (fail at load time, not at first resolve()).
            _parse_capability(entry, schema=schema)
            fallback = entry.get("fallback")
            if fallback is not None:
                _parse_capability(fallback, schema=schema)
                if "model_id" not in fallback:
                    raise ValueError(f"{path}: fallback for {cls!r} is missing model_id")

    def supported_classes(self) -> tuple[str, ...]:
        return tuple(self._classes)

    def capability(self, reasoning_class: str) -> ModelCapability:
        """Return the capability record for a class's primary model."""
        entry = self._classes.get(reasoning_class)
        if entry is None:
            raise ReasoningPolicyError(
                f"provider {self.provider!r} has no mapping for reasoning class "
                f"{reasoning_class!r} (supported: {', '.join(self._classes)})"
            )
        return _parse_capability(entry, schema=self.schema)

    def resolve(self, reasoning_class: str, *, live: bool = True) -> ModelSpec:
        entry = self._classes.get(reasoning_class)
        if entry is None:
            raise ReasoningPolicyError(
                f"provider {self.provider!r} has no mapping for reasoning class "
                f"{reasoning_class!r} (supported: {', '.join(self._classes)})"
            )
        cap = _parse_capability(entry, schema=self.schema)

        if not cap.fails_closed():
            return ModelSpec(
                provider=self.provider,
                model_id=entry["model_id"],
                reasoning_class=reasoning_class,
                effort=entry.get("effort"),
                lifecycle=cap.lifecycle,
                verified=cap.verified,
            )

        reason = (
            f"provider {self.provider!r} model {entry['model_id']!r} for reasoning class "
            f"{reasoning_class!r} is lifecycle={cap.lifecycle!r} verified={cap.verified} "
            "— refusing to resolve"
        )

        if live:
            # Fail closed. Try one (non-chaining) fallback before giving up —
            # ponytail: one level only, no fallback-of-a-fallback graph walk.
            fallback = entry.get("fallback")
            if fallback is not None:
                fb_cap = _parse_capability(fallback, schema=self.schema)
                if not fb_cap.fails_closed():
                    return ModelSpec(
                        provider=fallback.get("provider", self.provider),
                        model_id=fallback["model_id"],
                        reasoning_class=reasoning_class,
                        effort=entry.get("effort"),
                        lifecycle=fb_cap.lifecycle,
                        verified=fb_cap.verified,
                        warning=f"primary model unavailable ({reason}); used fallback",
                    )
            raise ReasoningPolicyError(f"{reason} (live call)")

        # Non-live (dry-run / local validation) path: degrade with a
        # recorded warning instead of raising. Nothing is sent anywhere.
        return ModelSpec(
            provider=self.provider,
            model_id=entry["model_id"],
            reasoning_class=reasoning_class,
            effort=entry.get("effort"),
            lifecycle=cap.lifecycle,
            verified=cap.verified,
            warning=f"{reason} (dry-run — proceeding)",
        )
