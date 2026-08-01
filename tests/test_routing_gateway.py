"""SHR-59: the model-call gateway is mandatory, not advisory.

The AST scan at the bottom is the actual guarantee. The gateway is only a
helper until something fails the build when a caller steps around it.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from shiroe.core.reasoning import ReasoningPolicyError
from shiroe.routing.gateway import (
    ModelCallRequest,
    RouteDecision,
    RoutingError,
    route,
)

REPO = Path(__file__).resolve().parents[1]

# Only these modules may resolve a provider model directly. Everything else
# goes through shiroe.routing.gateway.route().
DIRECT_RESOLUTION_ALLOWLIST = {
    "shiroe/routing/gateway.py",  # the gateway itself
    "shiroe/adapters/providers/__init__.py",  # resolve_model's own definition
    "shiroe/adapters/providers/base.py",  # ProviderAdapter.resolve's definition
}

GUARDED_NAMES = {"resolve_model"}


# --- entitlement is enforced at the gateway ---------------------------------


def test_low_criticality_cannot_buy_frontier() -> None:
    with pytest.raises(ReasoningPolicyError):
        route(ModelCallRequest(criticality="LOW", purpose="rename a variable",
                               requested_class="frontier"))


def test_critical_task_resolves_frontier() -> None:
    decision = route(ModelCallRequest(criticality="CRITICAL", purpose="benchmark verdict"))
    assert isinstance(decision, RouteDecision)
    assert decision.reasoning_class == "frontier"
    assert decision.entitled_class == "frontier"
    assert decision.model_spec.model_id


def test_downgrade_is_permitted() -> None:
    decision = route(ModelCallRequest(criticality="CRITICAL", purpose="cheap lookup",
                                      requested_class="fast"))
    assert decision.reasoning_class == "fast"
    assert decision.entitled_class == "frontier"  # entitlement is still recorded


def test_unknown_criticality_fails_closed() -> None:
    with pytest.raises(RoutingError):
        ModelCallRequest(criticality="URGENT", purpose="x")


def test_purpose_is_required() -> None:
    with pytest.raises(RoutingError):
        ModelCallRequest(criticality="LOW", purpose="   ")


# --- P1-07: placement and privacy are orthogonal to reasoning depth ---------


@pytest.mark.parametrize("placement_word", ["local", "private"])
def test_placement_is_not_accepted_as_a_reasoning_class(placement_word: str) -> None:
    """Regression: validate_request('LOW','private') and
    validate_request('CRITICAL','private') both returned 'private', throwing
    the criticality away. The gateway refuses the confusion."""
    with pytest.raises(RoutingError, match="is a placement, not a reasoning class"):
        ModelCallRequest(criticality="LOW", purpose="summarise",
                         requested_class=placement_word)


@pytest.mark.parametrize("placement_word", ["local", "private"])
def test_confined_placement_refuses_a_remote_model(placement_word: str) -> None:
    """A payload confined to this machine must not resolve to a remote model
    just because no local adapter exists."""
    with pytest.raises(RoutingError, match="local-execution provider adapter"):
        route(ModelCallRequest(criticality="CRITICAL", purpose="summarise a private project",
                               placement=placement_word))


def test_criticality_survives_privacy_class() -> None:
    low = route(ModelCallRequest(criticality="LOW", purpose="x", privacy_class="restricted"))
    critical = route(ModelCallRequest(criticality="CRITICAL", purpose="x",
                                      privacy_class="restricted"))
    assert low.reasoning_class == "fast"
    assert critical.reasoning_class == "frontier"
    assert low.model_spec.model_id != critical.model_spec.model_id


# --- decisions are auditable ------------------------------------------------


def test_decision_carries_provenance() -> None:
    decision = route(ModelCallRequest(criticality="MEDIUM", purpose="write a test"))
    assert decision.policy_version == "shiroe.routing.gateway/v1"
    assert len(decision.task_digest) == 16
    assert decision.purpose == "write a test"


def test_task_digest_is_stable_and_shape_sensitive() -> None:
    a = ModelCallRequest(criticality="LOW", purpose="x")
    b = ModelCallRequest(criticality="LOW", purpose="x")
    c = ModelCallRequest(criticality="HIGH", purpose="x")
    assert a.task_digest() == b.task_digest()
    assert a.task_digest() != c.task_digest()


# --- the guarantee ----------------------------------------------------------


def _python_sources() -> list[Path]:
    skip = {".git", "__pycache__", ".claude", "build", "dist", ".venv"}
    return [
        p
        for p in REPO.rglob("*.py")
        if not any(part in skip for part in p.parts)
        and "tests" not in p.parts
        and "benchmarks" not in p.parts
    ]


def _direct_resolution_calls(tree: ast.AST) -> list[str]:
    """Find calls that resolve a provider model without the gateway."""
    hits: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name) and func.id in GUARDED_NAMES:
            hits.append(f"{func.id}() at line {node.lineno}")
        elif isinstance(func, ast.Attribute) and func.attr in GUARDED_NAMES:
            hits.append(f".{func.attr}() at line {node.lineno}")
    return hits


def test_no_module_resolves_a_model_outside_the_gateway() -> None:
    offenders: dict[str, list[str]] = {}
    for path in _python_sources():
        rel = path.relative_to(REPO).as_posix()
        if rel in DIRECT_RESOLUTION_ALLOWLIST:
            continue
        hits = _direct_resolution_calls(ast.parse(path.read_text(encoding="utf-8")))
        if hits:
            offenders[rel] = hits
    assert not offenders, (
        "these modules resolve a provider model without passing through "
        "shiroe.routing.gateway.route(); route them or add a reviewed entry to "
        f"DIRECT_RESOLUTION_ALLOWLIST: {offenders}"
    )
