#!/usr/bin/env python3
"""migrate-v4.2-to-v4.3.py — Shiroe nomenclature migration.

v4.2 → v4.3 file layout alignment per SHIROE_OS §12.

Moves performed (all reversible via the pre-migration snapshot):
  memory/wiki/INDEX.md          → memory/index.md
  memory/wiki/DECISIONS.md      → memory/DECISIONS.md
  memory/wiki/OPEN_QUESTIONS.md → memory/OPEN_QUESTIONS.md
  memory/wiki/RISKS.md          → memory/RISKS.md
  memory/wiki/CONFLICTS.md      → memory/CONFLICTS.md
  memory/wiki/ARCHIVE/          → memory/archive/  (lowercased)
  memory/logs/session-events.jsonl → memory/archive/session-events-v4.2.jsonl
  config/PRIVACY.md             → memory/archive/config-PRIVACY-v4.2.md
                                   (root PRIVACY.md is authored separately; this only archives the old one)

Files created:
  memory/hot.md                  (≤500-word scaffold)
  memory/MEMORY.md               (agent-written session notes scaffold)
  memory/patterns/PATTERNS.jsonl (empty; pattern-observer target)

Policy:
  - Dry-run by DEFAULT. Pass --apply to write changes.
  - Idempotent: re-runs detect already-migrated state and exit cleanly.
  - Never hard delete. Originals are git-mv'd (history preserved) or archived.
  - Pre-migration snapshot lands in memory/archive/pre-v4.3-<iso>/ for rollback.
"""
from __future__ import annotations

import argparse
import datetime as dt
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# (src, dst) — flat memory/ layout per package §12
WIKI_MOVES = [
    ("memory/wiki/INDEX.md",          "memory/index.md"),
    ("memory/wiki/DECISIONS.md",      "memory/DECISIONS.md"),
    ("memory/wiki/OPEN_QUESTIONS.md", "memory/OPEN_QUESTIONS.md"),
    ("memory/wiki/RISKS.md",          "memory/RISKS.md"),
    ("memory/wiki/CONFLICTS.md",      "memory/CONFLICTS.md"),
]
DIR_MOVES = [
    ("memory/wiki/ARCHIVE", "memory/archive"),
]
ARCHIVE_MOVES = [
    # (src, dst)  — preserved-as-archive (history continuity broken intentionally)
    ("memory/logs/session-events.jsonl", "memory/archive/session-events-v4.2.jsonl"),
    ("config/PRIVACY.md",                "memory/archive/config-PRIVACY-v4.2.md"),
]
NEW_FILES = {
    "memory/hot.md": """<!-- memory/hot.md — last 3 sessions, current context. Cap ≤500 words.

Per SHIROE_OS §0: read FIRST on every session start. If insufficient, fall through to memory/index.md.

Format suggestion:
- ## Session <iso-date> — <one-line purpose>
- 3-5 bullet recap
- carry-forward open questions / decisions still in flight
-->

## Current context

(empty — populated by /done at session end)
""",
    "memory/MEMORY.md": """<!-- memory/MEMORY.md — agent-written session notes (NOT human-edited).

Per SHIROE_OS §3.4:
- AGENTS.md = human-written, agent-read (rules, policy)
- MEMORY.md = agent-written, agent-read (session notes, trap avoidance)
- First 200 lines auto-load on session start.
- Rule: treat your own memory as a hint, not a fact. Verify against actual code before acting.
- Auto-hygiene: convert relative time anchors to absolute dates on every /stop.
-->

## Notes

(empty — agents append on /stop)
""",
    "memory/patterns/PATTERNS.jsonl": "",  # empty append-only log
}
SESSION_EVENTS_HEADER = (
    '{"ts": "__TS__", "agent": "migrate-v4.2-to-v4.3", '
    '"event": "log-cutover", "target": "memory/patterns/PATTERNS.jsonl", '
    '"payload": {"predecessor": "memory/archive/session-events-v4.2.jsonl", '
    '"reason": "v4.3 flat memory layout per SHIROE_OS §12"}}\n'
)
WIKI_TOMBSTONE = """<!-- memory/wiki/ moved to flat memory/ layout in v4.3 (SHIROE_OS §12).
- INDEX.md          → memory/index.md
- DECISIONS.md      → memory/DECISIONS.md
- OPEN_QUESTIONS.md → memory/OPEN_QUESTIONS.md
- RISKS.md          → memory/RISKS.md
- CONFLICTS.md      → memory/CONFLICTS.md
- ARCHIVE/          → memory/archive/
Originals preserved via git history. -->
"""


def log(msg: str, dry: bool) -> None:
    prefix = "[DRY] " if dry else "[APPLY] "
    print(prefix + msg)


def have_git() -> bool:
    try:
        subprocess.run(["git", "rev-parse", "--is-inside-work-tree"],
                       cwd=ROOT, check=True, capture_output=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def is_tracked(path: Path) -> bool:
    try:
        result = subprocess.run(
            ["git", "ls-files", "--error-unmatch", str(path.relative_to(ROOT))],
            cwd=ROOT, capture_output=True,
        )
        return result.returncode == 0
    except Exception:
        return False


def move(src: Path, dst: Path, *, dry: bool, use_git: bool) -> None:
    if not src.exists():
        log(f"skip move (src missing): {src.relative_to(ROOT)}", dry)
        return
    if dst.exists():
        log(f"skip move (dst exists, idempotent): {dst.relative_to(ROOT)}", dry)
        return
    log(f"move: {src.relative_to(ROOT)} → {dst.relative_to(ROOT)}", dry)
    if dry:
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    if use_git and is_tracked(src):
        subprocess.run(
            ["git", "mv", str(src.relative_to(ROOT)), str(dst.relative_to(ROOT))],
            cwd=ROOT, check=True,
        )
    else:
        if src.is_dir():
            shutil.move(str(src), str(dst))
        else:
            shutil.move(str(src), str(dst))


def write_new(path: Path, content: str, *, dry: bool) -> None:
    if path.exists():
        log(f"skip create (already exists, idempotent): {path.relative_to(ROOT)}", dry)
        return
    log(f"create: {path.relative_to(ROOT)}", dry)
    if dry:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def snapshot(dest: Path, *, dry: bool) -> None:
    src = ROOT / "memory"
    log(f"snapshot memory/ → {dest.relative_to(ROOT)}", dry)
    if dry:
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    # Skip any existing pre-v4.3-* snapshots and the destination itself to avoid recursion
    # when dest lives under src.
    def _ignore(dirpath, names):
        skip = set()
        for n in names:
            if n.startswith("pre-v4.3-"):
                skip.add(n)
            full = Path(dirpath) / n
            try:
                if full.resolve() == dest.resolve():
                    skip.add(n)
            except OSError:
                pass
        return skip
    shutil.copytree(src, dest, ignore=_ignore)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true",
                        help="Actually perform the migration (default is dry-run).")
    parser.add_argument("--no-git", action="store_true",
                        help="Use shutil.move instead of git mv (skips history preservation).")
    args = parser.parse_args()

    dry = not args.apply
    use_git = (not args.no_git) and have_git()

    iso = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    print(f"\n=== migrate-v4.2-to-v4.3.py ({'DRY-RUN' if dry else 'APPLY'}) ===")
    print(f"repo root: {ROOT}")
    print(f"git mv: {'yes' if use_git else 'no'}")
    print()

    # 1. snapshot — placed under memory/snapshots/ to avoid colliding with the
    # memory/wiki/ARCHIVE → memory/archive rename below.
    snap = ROOT / f"memory/snapshots/pre-v4.3-{iso}"
    if (ROOT / "memory").exists():
        snapshot(snap, dry=dry)

    # 2. wiki flat moves
    for src_rel, dst_rel in WIKI_MOVES:
        move(ROOT / src_rel, ROOT / dst_rel, dry=dry, use_git=use_git)

    # 3. ARCHIVE dir → archive (lowercase)
    for src_rel, dst_rel in DIR_MOVES:
        move(ROOT / src_rel, ROOT / dst_rel, dry=dry, use_git=use_git)

    # 4. archive moves (session-events.jsonl, config/PRIVACY.md)
    for src_rel, dst_rel in ARCHIVE_MOVES:
        move(ROOT / src_rel, ROOT / dst_rel, dry=dry, use_git=use_git)

    # 5. drop wiki tombstone
    wiki_dir = ROOT / "memory/wiki"
    if wiki_dir.exists():
        # check empty (post-move)
        remaining = [p for p in wiki_dir.rglob("*") if p.is_file() and p.name != ".gitkeep"]
        if not remaining:
            tombstone = wiki_dir / "README-MOVED.md"
            if not tombstone.exists():
                log(f"create tombstone: {tombstone.relative_to(ROOT)}", dry)
                if not dry:
                    tombstone.write_text(WIKI_TOMBSTONE, encoding="utf-8")
        else:
            log(f"WARN: memory/wiki/ still has files: {[p.name for p in remaining]}", dry)

    # 6. scaffolds for new layout
    for rel, content in NEW_FILES.items():
        write_new(ROOT / rel, content, dry=dry)

    # 7. cutover marker in fresh PATTERNS.jsonl
    patterns = ROOT / "memory/patterns/PATTERNS.jsonl"
    needs_marker = (
        patterns.exists()
        and patterns.read_text(encoding="utf-8") == ""
        and (ROOT / "memory/archive/session-events-v4.2.jsonl").exists()
    )
    if needs_marker:
        ts = dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")
        marker = SESSION_EVENTS_HEADER.replace("__TS__", ts)
        log(f"append cutover marker to PATTERNS.jsonl", dry)
        if not dry:
            patterns.write_text(marker, encoding="utf-8")

    print()
    if dry:
        print("DRY-RUN complete. Re-run with --apply to perform the migration.")
    else:
        print("Migration complete. Verify with `git status` and `scripts/shiroe-validate-v4.py`.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
