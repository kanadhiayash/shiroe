"""CLI subcommands for ``zeref providers``.

Split from ``zeref.cli`` to keep that module from ballooning further, same
pattern as ``zeref.cli_capability``. Registered via ``register(sub)`` and
``handle(args)``.
"""

from __future__ import annotations

import argparse
import json

from zeref.adapters.providers import available_providers
from zeref.security import ConnectorDisabledError, NetworkDeniedError


def register(sub) -> None:
    p = sub.add_parser("providers", help="Provider model registry (ZRF-60)")
    psub = p.add_subparsers(dest="providers_command", required=True)

    rf = psub.add_parser(
        "refresh",
        help="Refresh model existence/lifecycle from the provider's list-models "
             "endpoint (opt-in; disabled unless the provider_refresh connector "
             "is enabled)",
    )
    rf.add_argument("--provider", required=True, choices=available_providers())
    rf.add_argument("--json", action="store_true")


def handle(args: argparse.Namespace) -> int:
    if args.providers_command == "refresh":
        from zeref.adapters.providers.refresh import refresh_provider

        try:
            result = refresh_provider(args.provider)
        except (ConnectorDisabledError, NetworkDeniedError) as exc:
            print(f"✘ refresh refused: {exc}")
            return 1
        if args.json:
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0
        print(f"providers refresh: {result['provider']} via {result['endpoint']}")
        print(f"  checked_at={result['checked_at']} ids_seen={result['ids_seen']} "
              f"response_digest={result['response_digest']}")
        if result["changed"]:
            for c in result["changed"]:
                print(f"  changed: {c['class']} ({c['model_id']}) "
                      f"{c['lifecycle']['from']} -> {c['lifecycle']['to']}")
        else:
            print("  no lifecycle changes")
        print(f"  not checked (no machine-readable source): "
              f"{', '.join(result['stale_fields_not_checked'])}")
        return 0

    print("✘ unknown providers command")
    return 1
