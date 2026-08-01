"""CLI subcommands for ``shiroe capability``.

Split from ``shiroe.cli`` to keep that module from ballooning further.
Registered from ``shiroe.cli`` via ``register(sub)`` and ``handle(args)``.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from shiroe.capabilities import (
    CapabilityStore,
    approve,
    assert_executable,
    discover,
    inspect_source,
    register_discovery,
    revoke,
)
from shiroe.capabilities.gate import CapabilityGateError


def _root() -> Path:
    from shiroe.memory import MemoryRoot
    return MemoryRoot.discover().root


def register(sub) -> None:
    p = sub.add_parser("capability", help="Capability registry & lifecycle (vNext §8)")
    csub = p.add_subparsers(dest="capability_command", required=True)

    d = csub.add_parser("discover", help="Scan configured roots")
    d.add_argument("--json", action="store_true")

    ls = csub.add_parser("list", help="List registered capabilities")
    ls.add_argument("--json", action="store_true")

    ins = csub.add_parser("inspect", help="Trust report for a source path")
    ins.add_argument("path")

    ap = csub.add_parser("approve", help="Approve a quarantined capability")
    ap.add_argument("capability_id")

    rv = csub.add_parser("revoke", help="Revoke a capability")
    rv.add_argument("capability_id")

    rf = csub.add_parser("refresh", help="Rehash source; drift → quarantine")
    rf.add_argument("capability_id")

    tr = csub.add_parser("trust-report", help="Emit stored trust report JSON")
    tr.add_argument("capability_id")

    ex = csub.add_parser("gate", help="Assert a capability is executable (exit 0) or raise (exit 2)")
    ex.add_argument("capability_id")

    pr = csub.add_parser("probe", help="Health-check the adapter for a capability")
    pr.add_argument("capability_id")

    ad = csub.add_parser("adapters", help="List registered capability adapters")
    ad.add_argument("--json", action="store_true")


def handle(args: argparse.Namespace) -> int:
    root = _root()
    cmd = args.capability_command

    if cmd == "discover":
        results = discover(root)
        registered: list[str] = []
        for r in results:
            trust = inspect_source(r.path)
            cid = register_discovery(root, r, trust=trust)
            registered.append(cid)
        if args.json:
            print(json.dumps({"discovered": len(results),
                              "registered": registered}, indent=2))
        else:
            print(f"discovered {len(results)}; registered {len(registered)}")
            for cid in registered:
                print(f"  {cid}")
        return 0

    if cmd == "list":
        store = CapabilityStore(root)
        rows = store.list()
        store.close()
        if args.json:
            print(json.dumps(rows, indent=2))
        else:
            for r in rows:
                print(f"{r['lifecycle']:<12} {r['type']:<10} {r['id']}")
        return 0

    if cmd == "inspect":
        report = inspect_source(Path(args.path))
        print(json.dumps(report.to_dict(), indent=2))
        return 0

    if cmd == "approve":
        approve(root, args.capability_id)
        print(f"approved: {args.capability_id}")
        return 0

    if cmd == "revoke":
        revoke(root, args.capability_id)
        print(f"revoked: {args.capability_id}")
        return 0

    if cmd == "refresh":
        store = CapabilityStore(root)
        row = store.get(args.capability_id)
        if row is None:
            print(f"unknown: {args.capability_id}"); store.close(); return 1
        version = store.conn.execute(
            "SELECT source_location FROM capability_versions "
            "WHERE capability_id=? ORDER BY created_at DESC LIMIT 1",
            (args.capability_id,),
        ).fetchone()
        if version is None:
            print(f"no version record for {args.capability_id}"); store.close(); return 1
        trust = inspect_source(Path(version[0]))
        new_state = store.refresh_digest(args.capability_id, trust.digest)
        store.close()
        print(f"digest: {trust.digest}  lifecycle: {new_state}")
        return 0

    if cmd == "trust-report":
        store = CapabilityStore(root)
        version = store.conn.execute(
            "SELECT manifest, source_location FROM capability_versions "
            "WHERE capability_id=? ORDER BY created_at DESC LIMIT 1",
            (args.capability_id,),
        ).fetchone()
        if version is None:
            print(f"no version record for {args.capability_id}"); store.close(); return 1
        trust = inspect_source(Path(version[1]))
        print(json.dumps({
            "capability_id": args.capability_id,
            "manifest": json.loads(version[0]),
            "trust": trust.to_dict(),
        }, indent=2))
        store.close()
        return 0

    if cmd == "gate":
        try:
            assert_executable(root, args.capability_id)
        except CapabilityGateError as e:
            print(f"DENY: {e}")
            return 2
        print(f"OK: {args.capability_id} is executable")
        return 0

    if cmd == "probe":
        from shiroe.adapters.capabilities import probe
        report = probe(root, args.capability_id)
        print(json.dumps({
            "adapter": report.adapter,
            "detected_version": report.detected_version,
            "enforcement_level": report.enforcement_level.value,
            "supported_features": list(report.supported_features),
            "healthy": report.healthy,
            "failure_reason": report.failure_reason,
        }, indent=2))
        return 0 if report.healthy else 2

    if cmd == "adapters":
        from shiroe.adapters.capabilities import list_adapters
        rows = list_adapters()
        if args.json:
            print(json.dumps(rows, indent=2))
        else:
            for r in rows:
                types = ",".join(r["supported_types"])
                print(f"{r['enforcement_level']}  {r['name']:<20} [{types}]")
        return 0

    return 1
