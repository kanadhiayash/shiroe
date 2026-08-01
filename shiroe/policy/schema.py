"""Types for the policy engine."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class ActionKind(str, Enum):
    fs_read = "fs.read"
    fs_write = "fs.write"
    fs_delete = "fs.delete"
    network = "network"
    secret_read = "secret.read"
    subprocess = "subprocess"
    external_write = "external.write"
    destructive = "destructive"
    memory_write = "memory.write"
    event_write = "event.write"
    push = "vcs.push"
    merge = "vcs.merge"
    publish = "publish"
    external_message = "external.message"
    permission_change = "permission.change"
    budget_escalation = "budget.escalation"
    dependency_add = "dependency.add"
    capability_invoke = "capability.invoke"


class Verdict(str, Enum):
    allow = "allow"
    deny = "deny"
    require_approval = "require_approval"


@dataclass(frozen=True)
class Action:
    kind: ActionKind
    target: str = ""            # path, URL, secret name, capability id
    context: dict[str, Any] | None = None


@dataclass(frozen=True)
class Decision:
    verdict: Verdict
    reason: str
    deciding_layer: str          # e.g. "runtime-invariant", "project-deny", ...

    @property
    def allowed(self) -> bool:
        return self.verdict is Verdict.allow


@dataclass(frozen=True)
class PolicyLayer:
    name: str                    # "project-deny", "global-defaults", ...
    denies: frozenset[ActionKind] = frozenset()
    allows: frozenset[ActionKind] = frozenset()
    # For fs.write, network etc. we also allow scoped grants:
    fs_write_scopes: tuple[str, ...] = ()
    fs_read_scopes: tuple[str, ...] = ()
    network_hosts: tuple[str, ...] = ()
