"""MCP server adapter — subprocess launcher + JSON-RPC probe.

We launch the declared MCP server process, send a JSON-RPC ``initialize``
request over stdio, and record what came back. Full RPC bridging (call
``tools/list``, then ``tools/call``) is out of scope for PR 5 — the
supervisor (PR 8) will drive the multi-turn RPC via this same subprocess.
"""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

from zeref.adapters.capabilities.base import (
    AdapterResult,
    EnforcementLevel,
    HealthReport,
)
from zeref.capabilities.store import CapabilityStore
from zeref.policy import (
    Action, ActionKind, AutonomyMode, Verdict, evaluate, load_policy_stack,
)


class MCPServerAdapter:
    name = "mcp-server"
    enforcement_level = EnforcementLevel.embedded
    supported_types: tuple[str, ...] = ("mcp_server",)

    def health(self) -> HealthReport:
        return HealthReport(
            adapter=self.name,
            detected_version="1.0",
            enforcement_level=self.enforcement_level,
            supported_features=("jsonrpc_stdio", "initialize_probe"),
            healthy=True,
            supported_types=self.supported_types,
        )

    def invoke(self, *, capability_id: str, action: str, inputs: dict,
               permissions: dict | None = None,
               timeout_s: int | None = None) -> AdapterResult:
        if action != "initialize":
            return AdapterResult(
                ok=False,
                error=f"MCP adapter PR 5 supports only 'initialize'; got {action!r}. "
                      "Full RPC bridging lands in PR 8 supervisor.",
            )
        root = inputs.get("root")
        if root is None:
            return AdapterResult(ok=False, error="missing 'root' input")

        store = CapabilityStore(root)
        try:
            row = store.conn.execute(
                "SELECT source_location, manifest FROM capability_versions "
                "WHERE capability_id=? ORDER BY created_at DESC LIMIT 1",
                (capability_id,),
            ).fetchone()
        finally:
            store.close()
        if row is None:
            return AdapterResult(ok=False, error=f"no version record for {capability_id!r}")

        source = Path(row[0])
        manifest = json.loads(row[1] or "{}")
        launch = manifest.get("entrypoint", {}).get("command")
        if launch is None:
            # convention: server.py alongside the source
            candidate = source / "server.py"
            if not candidate.exists():
                return AdapterResult(
                    ok=False,
                    error="no entrypoint.command in manifest and no server.py in source",
                )
            argv = ["python3", str(candidate)]
        else:
            argv = [str(x) for x in launch] if isinstance(launch, list) else str(launch).split()

        # Policy gate — MCP servers are subprocesses.
        stack = load_policy_stack(root)
        mode = AutonomyMode(inputs.get("autonomy_mode", "auto-safe"))
        decision = evaluate(
            Action(ActionKind.subprocess, target=" ".join(argv),
                   context={"capability_id": capability_id, "kind": "mcp"}),
            stack, mode=mode,
        )
        if decision.verdict is not Verdict.allow:
            return AdapterResult(
                ok=False,
                error=f"policy {decision.verdict.value} at {decision.deciding_layer}: {decision.reason}",
                metadata={"policy": {
                    "verdict": decision.verdict.value,
                    "deciding_layer": decision.deciding_layer,
                }},
            )

        # Launch, send initialize, read one JSON line back, terminate.
        from zeref import __version__ as _zeref_version

        request = json.dumps({
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                       "clientInfo": {"name": "zeref", "version": _zeref_version}},
        })
        try:
            proc = subprocess.Popen(
                argv,
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, cwd=str(source if source.is_dir() else source.parent),
            )
        except FileNotFoundError as e:
            return AdapterResult(ok=False, error=f"launcher not found: {e}")

        deadline = time.monotonic() + (timeout_s or 10)
        try:
            assert proc.stdin is not None and proc.stdout is not None
            proc.stdin.write(request + "\n")
            proc.stdin.flush()
            line = ""
            while time.monotonic() < deadline:
                if proc.poll() is not None:
                    break
                line = proc.stdout.readline()
                if line:
                    break
                time.sleep(0.05)
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()

        if not line.strip():
            return AdapterResult(
                ok=False, error="no response from MCP server before timeout",
                stderr_tail=(proc.stderr.read()[-2000:] if proc.stderr else None),
            )
        try:
            response = json.loads(line)
        except json.JSONDecodeError as e:
            return AdapterResult(
                ok=False, error=f"non-JSON response: {e}",
                metadata={"raw": line[:500]},
            )
        return AdapterResult(
            ok=("result" in response),
            output=response.get("result"),
            error=None if "result" in response else str(response.get("error")),
            metadata={"enforcement_level": self.enforcement_level.value,
                      "argv": argv,
                      "policy": {"verdict": decision.verdict.value,
                                 "deciding_layer": decision.deciding_layer}},
        )
