"""CLI adapter — invoke an approved CLI capability via subprocess.

Enforcement is Level A: we own the subprocess. Every invocation routes
through ``shiroe.policy.evaluate`` with an ``ActionKind.subprocess`` and,
if the capability declares an outbound host, ``ActionKind.network``. No
bypass path exists.
"""

from __future__ import annotations

import json
import shlex
import subprocess
from pathlib import Path
from typing import Any

from shiroe.adapters.capabilities.base import (
    AdapterResult,
    EnforcementLevel,
    HealthReport,
)
from shiroe.capabilities.store import CapabilityStore
from shiroe.policy import Action, ActionKind, AutonomyMode, Verdict, evaluate, load_policy_stack


class CLIAdapter:
    name = "cli"
    enforcement_level = EnforcementLevel.embedded
    supported_types: tuple[str, ...] = ("cli", "script")

    def health(self) -> HealthReport:
        return HealthReport(
            adapter=self.name,
            detected_version="1.0",
            enforcement_level=self.enforcement_level,
            supported_features=("subprocess", "policy_gated", "timeout"),
            healthy=True,
            supported_types=self.supported_types,
        )

    def invoke(self, *, capability_id: str, action: str, inputs: dict,
               permissions: dict | None = None,
               timeout_s: int | None = None) -> AdapterResult:
        root = inputs.get("root")
        if root is None:
            return AdapterResult(ok=False, error="missing 'root' input")

        # 1. Resolve source location
        store = CapabilityStore(root)
        try:
            row = store.conn.execute(
                "SELECT source_location FROM capability_versions "
                "WHERE capability_id=? ORDER BY created_at DESC LIMIT 1",
                (capability_id,),
            ).fetchone()
        finally:
            store.close()
        if row is None:
            return AdapterResult(
                ok=False, error=f"no version record for {capability_id!r}",
            )
        source = Path(row[0])

        # 2. Resolve command
        raw_cmd = inputs.get("command")
        if raw_cmd is None:
            # default: exec the source as a script
            if source.is_file():
                argv: list[str] = [str(source)] + list(inputs.get("args", ()))
            else:
                return AdapterResult(
                    ok=False,
                    error=f"no 'command' provided and source {source} is not a script",
                )
        elif isinstance(raw_cmd, list):
            argv = [str(x) for x in raw_cmd]
        else:
            argv = shlex.split(str(raw_cmd))

        # 3. Policy check — always. Every subprocess flows through here.
        stack = load_policy_stack(root)
        mode = AutonomyMode(inputs.get("autonomy_mode", "auto-safe"))
        decision = evaluate(
            Action(ActionKind.subprocess,
                   target=" ".join(argv),
                   context={"capability_id": capability_id}),
            stack, mode=mode,
        )
        if decision.verdict is not Verdict.allow:
            return AdapterResult(
                ok=False,
                error=f"policy {decision.verdict.value} at {decision.deciding_layer}: {decision.reason}",
                metadata={"policy": {
                    "verdict": decision.verdict.value,
                    "reason": decision.reason,
                    "deciding_layer": decision.deciding_layer,
                }},
            )

        # 4. Command allowlist (from declared permissions)
        allow_commands = _string_list(permissions, "allow_commands")
        if allow_commands and argv[0] not in allow_commands:
            return AdapterResult(
                ok=False,
                error=f"command {argv[0]!r} not in capability allowlist "
                      f"{sorted(allow_commands)}",
            )

        # 5. Execute
        try:
            completed = subprocess.run(
                argv,
                capture_output=True,
                text=True,
                timeout=timeout_s or 60,
                cwd=str(source.parent if source.is_file() else source),
            )
        except subprocess.TimeoutExpired as e:
            return AdapterResult(
                ok=False, error=f"timeout after {e.timeout}s",
                stderr_tail=(e.stderr or "")[-2000:] if isinstance(e.stderr, str) else None,
            )
        except FileNotFoundError as e:
            return AdapterResult(ok=False, error=f"executable not found: {e}")

        return AdapterResult(
            ok=completed.returncode == 0,
            output=_try_json(completed.stdout),
            exit_code=completed.returncode,
            stderr_tail=completed.stderr[-2000:] if completed.stderr else None,
            metadata={
                "argv": argv,
                "enforcement_level": self.enforcement_level.value,
                "policy": {"verdict": decision.verdict.value,
                           "deciding_layer": decision.deciding_layer},
            },
        )


def _try_json(text: str) -> Any:
    text = (text or "").strip()
    if not text:
        return ""
    if text.startswith(("{", "[")):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text
    return text


def _string_list(permissions: dict | None, key: str) -> list[str]:
    if not permissions:
        return []
    raw = permissions.get(key) or []
    return [str(x) for x in raw]
