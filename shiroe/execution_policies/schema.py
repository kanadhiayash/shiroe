"""Execution-policy schema + validator."""

from __future__ import annotations

from dataclasses import dataclass, field


POLICY_SCHEMA = "shiroe.policy/v1"
POLICY_IDS = ("lean", "balanced", "assured")

_REQUIRED = (
    "max_parallel_workers", "max_capabilities", "independent_verifiers",
    "autonomy_default", "reasoning_class_limits", "cost_envelope",
)


class PolicySchemaError(ValueError):
    pass


@dataclass
class ExecutionPolicy:
    id: str
    version: int
    max_parallel_workers: int
    max_capabilities: int
    independent_verifiers: int
    autonomy_default: str
    reasoning_class_limits: dict
    cost_envelope: dict
    description: str = ""


def validate(data: dict) -> ExecutionPolicy:
    if data.get("schema") != POLICY_SCHEMA:
        raise PolicySchemaError(
            f"expected schema {POLICY_SCHEMA!r}, got {data.get('schema')!r}"
        )
    for k in ("id", "version", *_REQUIRED):
        if k not in data:
            raise PolicySchemaError(f"missing field {k!r}")
    if data["id"] not in POLICY_IDS:
        raise PolicySchemaError(
            f"policy id must be one of {POLICY_IDS}; got {data['id']!r}"
        )
    if data["autonomy_default"] not in ("suggest", "auto-safe", "policy-bound"):
        raise PolicySchemaError(
            f"autonomy_default must be one of "
            f"suggest / auto-safe / policy-bound; got {data['autonomy_default']!r}"
        )
    for cls in ("fast", "balanced", "deep", "frontier"):
        if cls not in data["reasoning_class_limits"]:
            raise PolicySchemaError(f"reasoning_class_limits missing {cls!r}")
    for k in ("usd_max", "tokens_input_max", "tokens_output_max"):
        if k not in data["cost_envelope"]:
            raise PolicySchemaError(f"cost_envelope missing {k!r}")
    return ExecutionPolicy(
        id=str(data["id"]),
        version=int(data["version"]),
        max_parallel_workers=int(data["max_parallel_workers"]),
        max_capabilities=int(data["max_capabilities"]),
        independent_verifiers=int(data["independent_verifiers"]),
        autonomy_default=str(data["autonomy_default"]),
        reasoning_class_limits=dict(data["reasoning_class_limits"]),
        cost_envelope=dict(data["cost_envelope"]),
        description=str(data.get("description") or ""),
    )
