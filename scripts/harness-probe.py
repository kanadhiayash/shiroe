#!/usr/bin/env python3
"""
harness-probe.py — Detect the host AI harness and validate the surface
Zeref expects to find.

Detection heuristics:
    Claude Code   → CLAUDE.md present + claude binary on PATH
    Codex         → CODEX.md present or AGENTS.md only
    Cursor        → .cursor/ present
    Windsurf      → .windsurfrules present
    Aider         → .aider.conf.yml / .aider.conf.yml.example
    Gemini CLI    → GEMINI.md present
    LLama harness → LLAMA.md present

For each detected harness we check the minimum surface (canonical AGENTS.md
defer, per-harness stub, optional binary on PATH) and emit a report.

Exit code: 0 unless --all is passed and any required surface is missing.

Usage:
    python3 scripts/harness-probe.py
    python3 scripts/harness-probe.py --all
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path


def _root() -> Path:
    p = Path.cwd()
    for _ in range(10):
        if (p / "AGENTS.md").exists():
            return p
        p = p.parent
    return Path.cwd()


HARNESSES: list[dict] = [
    {"name": "claude-code", "stub": "CLAUDE.md",                 "bin": "claude"},
    {"name": "codex",       "stub": "CODEX.md",                  "bin": "codex"},
    {"name": "cursor",      "stub": ".cursor/rules/zeref.mdc",   "bin": "cursor"},
    {"name": "windsurf",    "stub": ".windsurfrules",            "bin": "windsurf"},
    {"name": "aider",       "stub": ".aider.conf.yml.example",   "bin": "aider"},
    {"name": "gemini",      "stub": "GEMINI.md",                 "bin": "gemini"},
    {"name": "llama",       "stub": "LLAMA.md",                  "bin": None},
]


def probe(root: Path) -> list[dict]:
    out: list[dict] = []
    canonical_ok = (root / "AGENTS.md").exists()
    for h in HARNESSES:
        stub_path = root / h["stub"]
        out.append({
            "harness":   h["name"],
            "stub":      h["stub"],
            "stub_ok":   stub_path.exists(),
            "agents_md": canonical_ok,
            "bin_ok":    bool(h["bin"] and shutil.which(h["bin"])),
            "bin":       h["bin"],
        })
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--all", action="store_true",
                    help="Fail (exit 1) if any harness stub is missing.")
    ap.add_argument("--json", action="store_true",
                    help="Emit a machine-readable JSON report.")
    args = ap.parse_args()

    root = _root()
    report = probe(root)

    if args.json:
        print(json.dumps({
            "root": str(root),
            "agents_md": (root / "AGENTS.md").exists(),
            "harnesses": report,
        }, indent=2))
    else:
        print(f"AGENTS.md (canonical): {'OK' if (root / 'AGENTS.md').exists() else 'MISSING'}")
        for r in report:
            print(
                f"  [{r['harness']:<12}] stub={r['stub']:<32} "
                f"present={'Y' if r['stub_ok'] else 'N'}  "
                f"bin={'Y' if r['bin_ok'] else 'N'}"
            )

    if args.all:
        missing = [r["harness"] for r in report if not r["stub_ok"]]
        if missing:
            print(f"\nMissing stubs: {', '.join(missing)}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
