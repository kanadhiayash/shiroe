"""The mandatory model-call gateway.

Every model call passes through :func:`route`. Nothing else may resolve a
provider model: ``resolve_model`` and ``ProviderAdapter.resolve`` are internal
edges, and ``tests/test_routing_gateway.py`` fails the build if any module
outside the allowlist calls them directly.

A policy that a caller can step around is a helper, not a guarantee. The
guarantee here is structural:

- A call carries a *criticality*, never a bare model id and never a bare
  reasoning class.
- Entitlement is checked before resolution, not after.
- *Placement* (where the call may execute) and *privacy class* are separate
  fields from *reasoning class* (how much reasoning the task may buy). They
  are orthogonal concerns and one must never silently stand in for the other.

privacy-audit: allow-file "Gateway names reasoning classes and placement
vocabulary; no user data."
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from zeref.adapters.providers import DEFAULT_PROVIDER, resolve_model
from zeref.core.reasoning import (
    LOCAL,
    PRIVATE,
    CRITICALITIES,
    ModelSpec,
    ReasoningPolicyError,
    resolve_class,
    validate_request,
)

POLICY_VERSION = "zeref.routing.gateway/v1"

# Where a call may execute. Orthogonal to reasoning class: a CRITICAL task
# pinned to local execution is still a CRITICAL task and keeps its
# entitlement. Before this gateway, asking for the ``private`` reasoning
# class returned ``private`` and threw the criticality away.
ANY = "any"
PLACEMENTS: tuple[str, ...] = (ANY, LOCAL, PRIVATE)

# Sensitivity of the payload, per the repository classification vocabulary.
PRIVACY_CLASSES: tuple[str, ...] = ("public", "internal", "confidential", "restricted")


class RoutingError(ReasoningPolicyError):
    """Raised when a request cannot be routed under current policy."""


@dataclass(frozen=True)
class ModelCallRequest:
    """The only accepted description of an intended model call."""

    criticality: str
    purpose: str
    requested_class: str | None = None
    placement: str = ANY
    privacy_class: str = "internal"
    provider: str = DEFAULT_PROVIDER

    def __post_init__(self) -> None:
        if self.criticality.upper() not in CRITICALITIES:
            raise RoutingError(
                f"unknown criticality {self.criticality!r}; expected one of {CRITICALITIES}"
            )
        if not self.purpose.strip():
            raise RoutingError("purpose is required: every routed call must say why it exists")
        if self.placement not in PLACEMENTS:
            raise RoutingError(
                f"unknown placement {self.placement!r}; expected one of {PLACEMENTS}"
            )
        if self.privacy_class not in PRIVACY_CLASSES:
            raise RoutingError(
                f"unknown privacy class {self.privacy_class!r}; expected one of {PRIVACY_CLASSES}"
            )
        # Placement is not a reasoning class. Accepting it here is what let
        # criticality be discarded, so the gateway refuses the confusion
        # outright rather than quietly honouring it.
        if self.requested_class in (LOCAL, PRIVATE):
            raise RoutingError(
                f"{self.requested_class!r} is a placement, not a reasoning class; "
                f"pass placement={self.requested_class!r} and state the reasoning class separately"
            )

    def task_digest(self) -> str:
        """Stable, privacy-safe identifier for this call shape."""
        material = "|".join(
            (
                self.criticality.upper(),
                self.purpose,
                self.requested_class or "-",
                self.placement,
                self.privacy_class,
                self.provider,
            )
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class RouteDecision:
    """The audit record of a routing decision, returned to the caller."""

    model_spec: ModelSpec
    criticality: str
    entitled_class: str
    reasoning_class: str
    placement: str
    privacy_class: str
    provider: str
    purpose: str
    task_digest: str
    policy_version: str = POLICY_VERSION


def route(request: ModelCallRequest) -> RouteDecision:
    """Validate a request against policy and resolve it to a concrete model.

    Raises :class:`RoutingError` rather than returning a degraded decision.
    Failing closed is the point: a caller that cannot be routed safely must
    not receive a model.
    """
    criticality = request.criticality.upper()
    entitled = resolve_class(criticality)

    if request.requested_class is None:
        granted = entitled
    else:
        # Raises when the request tries to buy more reasoning than the
        # criticality entitles. Downgrades are always permitted.
        granted = validate_request(criticality, request.requested_class)

    if request.placement in (LOCAL, PRIVATE):
        # No local-execution provider adapter is registered. Resolving a
        # remote model here would send a payload the caller explicitly
        # confined to this machine.
        raise RoutingError(
            f"placement={request.placement!r} requires a local-execution provider adapter; "
            f"none is registered, so refusing to resolve a remote model for "
            f"{request.purpose!r}"
        )

    spec = resolve_model(granted, provider=request.provider)

    return RouteDecision(
        model_spec=spec,
        criticality=criticality,
        entitled_class=entitled,
        reasoning_class=granted,
        placement=request.placement,
        privacy_class=request.privacy_class,
        provider=request.provider,
        purpose=request.purpose,
        task_digest=request.task_digest(),
    )
