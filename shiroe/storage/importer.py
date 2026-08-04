"""Importer — bring legacy v1 memory into SQLite v2 (vNext §6.5).

Sources handled:
- the v1 store under ``memory/state/`` (v1 ``memory_cards`` / ``memory_items``);
  its filename is :data:`~shiroe.compat.legacy_identity.LEGACY_V1_STATE_DB_NAME`
- ``memory/l1_atoms/*.jsonl`` (append-only atom stores)
- Root markdown surfaces (``memory/DECISIONS.md``, ``memory/RISKS.md``,
  ``memory/CONFLICTS.md``, ``memory/MEMORY.md``)

This is the migration path off the v1 store (SHR-016): the v1 file is read,
never renamed and never deleted, and its rows land in the Shiroe-named vNext
database. Store convergence — dropping the v1 file once its rows are in — is
issue #208.

Guarantees:
- Dry-run: side-effect-free with the same manifest that the real run would
  emit.
- Idempotent: re-running produces zero writes (records dedup by
  ``(source_type, source_ref, content_hash)``).
- Backup: ``memory/state/shiroe.sqlite`` copied to
  ``memory/state/backups/shiroe-<ts>.sqlite`` before any write.
- Rollback: restores the most recent backup, pre-rename backups included.
- Manifest: JSON with counts + hashes written to
  ``memory/state/imports/<ts>.json``.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from shiroe.compat.legacy_identity import (
    LEGACY_IMPORT_BACKUP_PREFIX,
    LEGACY_V1_STATE_DB_NAME,
)
from shiroe.storage.state import StateDB

BACKUP_PREFIX = "shiroe-"


@dataclass
class ImportManifest:
    timestamp: str
    dry_run: bool
    backup_path: str | None
    sources_scanned: dict[str, int] = field(default_factory=dict)
    records_written: int = 0
    records_skipped_duplicate: int = 0
    conflicts: list[dict] = field(default_factory=list)
    before_counts: dict[str, int] = field(default_factory=dict)
    after_counts: dict[str, int] = field(default_factory=dict)
    hashes: dict[str, str] = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(self.__dict__, indent=2, sort_keys=True)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _record_id(source_type: str, source_ref: str, content_hash: str) -> str:
    seed = f"{source_type}|{source_ref}|{content_hash}"
    return "mem_" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:20]


def _table_count(conn: sqlite3.Connection, table: str) -> int:
    try:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    except sqlite3.OperationalError:
        return 0


def _existing_ids(conn: sqlite3.Connection) -> set[str]:
    return {r[0] for r in conn.execute("SELECT id FROM memory_records")}


def _iter_atom_jsonl(root: Path) -> Iterable[tuple[str, dict]]:
    atom_dir = root / "memory" / "l1_atoms"
    if not atom_dir.exists():
        return
    for path in sorted(atom_dir.glob("*.jsonl")):
        rel = str(path.relative_to(root))
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield rel, json.loads(line)
                except json.JSONDecodeError:
                    continue


def _iter_markdown_records(root: Path) -> Iterable[tuple[str, str, str, str]]:
    """Yield (source_ref, kind, title, body) for headed sections of the four
    root markdown surfaces. Very forgiving: a section is a level-2 heading
    (``## Title``) plus the paragraph(s) that follow, until the next ``##`` or EOF.
    """
    kinds = {
        "memory/DECISIONS.md": "decision",
        "memory/RISKS.md": "risk",
        "memory/CONFLICTS.md": "contradiction",
        "memory/MEMORY.md": "note",
    }
    for rel, kind in kinds.items():
        path = root / rel
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        parts = text.split("\n## ")
        if not parts:
            continue
        # first chunk before any '## ' is preamble; skip.
        for chunk in parts[1:]:
            head, _, body = chunk.partition("\n")
            title = head.strip()
            if not title:
                continue
            yield rel, kind, title, body.strip()


def _iter_legacy_sqlite(root: Path) -> Iterable[tuple[str, dict]]:
    legacy = root / "memory" / "state" / LEGACY_V1_STATE_DB_NAME
    if not legacy.exists():
        return
    conn = sqlite3.connect(legacy)
    try:
        for table in ("memory_cards", "memory_items"):
            try:
                rows = conn.execute(f"SELECT * FROM {table}").fetchall()
                cols = [d[0] for d in conn.execute(f"SELECT * FROM {table} LIMIT 0").description]
            except sqlite3.OperationalError:
                continue
            for row in rows:
                yield table, dict(zip(cols, row))
    finally:
        conn.close()


def _insert_record(conn: sqlite3.Connection, *, id_: str, kind: str, title: str,
                   claim: str, summary: str, source_type: str, source_ref: str,
                   content_hash: str) -> None:
    now = _now()
    conn.execute(
        """
        INSERT INTO memory_records
            (id, kind, title, claim, summary, status, confidence,
             evidence_grade, privacy_class, authority, scope,
             valid_from, valid_until, created_at, updated_at, owner,
             schema_version, archived)
        VALUES (?, ?, ?, ?, ?, 'active', 'unknown',
                'unknown', 'internal', 0.0, 'project',
                NULL, NULL, ?, ?, 'importer',
                2, 0)
        """,
        (id_, kind, title, claim, summary, now, now),
    )
    conn.execute(
        """
        INSERT INTO memory_sources
            (id, memory_id, source_type, source_ref, source_digest,
             observed_at, retrieved_at, provenance)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'v1-importer')
        """,
        ("src_" + uuid.uuid4().hex[:16], id_, source_type, source_ref,
         "sha256:" + content_hash, now, now),
    )


def run_import(root: Path | str, *, dry_run: bool = True) -> ImportManifest:
    root = Path(root)
    db = StateDB(root)
    db.migrate()
    # Snapshot AFTER migrate but BEFORE any inserts so rollback restores the
    # pre-import current state (not a pre-migrate empty file).
    conn = db.connect()
    manifest = ImportManifest(
        timestamp=_now(),
        dry_run=dry_run,
        backup_path=None,
        before_counts={t: _table_count(conn, t) for t in ("memory_records", "memory_sources")},
    )

    if not dry_run:
        backup_dir = root / "memory" / "state" / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup = backup_dir / f"{BACKUP_PREFIX}{manifest.timestamp.replace(':','')}.sqlite"
        db.close()
        shutil.copy2(db.path, backup)
        manifest.backup_path = str(backup.relative_to(root))
        conn = db.connect()

    existing = _existing_ids(conn)
    counts = {"atom_jsonl": 0, "legacy_sqlite": 0, "markdown": 0}

    def _try_insert(source_type: str, source_ref: str, kind: str, title: str,
                    claim: str, summary: str) -> None:
        content_hash = _sha256(f"{title}\n{claim}\n{summary}")
        rid = _record_id(source_type, source_ref, content_hash)
        if rid in existing:
            manifest.records_skipped_duplicate += 1
            return
        existing.add(rid)
        if dry_run:
            manifest.records_written += 1
            return
        _insert_record(
            conn, id_=rid, kind=kind, title=title, claim=claim,
            summary=summary, source_type=source_type, source_ref=source_ref,
            content_hash=content_hash,
        )
        manifest.records_written += 1

    # 1. atom JSONL
    for rel, atom in _iter_atom_jsonl(root):
        counts["atom_jsonl"] += 1
        kind = str(atom.get("type") or atom.get("kind") or "note")
        title = str(atom.get("title") or atom.get("id") or "atom")
        claim = str(atom.get("claim") or atom.get("text") or "")
        summary = json.dumps({k: v for k, v in atom.items() if k not in ("claim", "text")},
                             sort_keys=True)[:2000]
        _try_insert("atom_jsonl", rel, kind, title, claim, summary)

    # 2. legacy SQLite
    for table, row in _iter_legacy_sqlite(root):
        counts["legacy_sqlite"] += 1
        title = str(row.get("title") or row.get("id") or table)
        claim = str(row.get("claim") or row.get("body") or row.get("summary") or "")
        summary = json.dumps({k: v for k, v in row.items() if k not in ("claim", "body")},
                             sort_keys=True, default=str)[:2000]
        _try_insert(f"legacy_sqlite/{table}", str(row.get("id") or ""),
                    "note", title, claim, summary)

    # 3. markdown
    for rel, kind, title, body in _iter_markdown_records(root):
        counts["markdown"] += 1
        _try_insert("markdown", rel, kind, title, body[:1500], body)

    manifest.sources_scanned = counts

    if not dry_run:
        conn.commit()
        manifest.after_counts = {t: _table_count(conn, t) for t in ("memory_records", "memory_sources")}
        # write manifest
        man_dir = root / "memory" / "state" / "imports"
        man_dir.mkdir(parents=True, exist_ok=True)
        man_path = man_dir / f"import-{manifest.timestamp.replace(':','')}.json"
        man_path.write_text(manifest.to_json(), encoding="utf-8")
    else:
        manifest.after_counts = manifest.before_counts

    manifest.hashes["schema_version"] = str(db.schema_version())
    db.close()
    return manifest


def rollback(root: Path | str) -> Path:
    root = Path(root)
    db = StateDB(root)
    backup_dir = root / "memory" / "state" / "backups"
    # Both prefixes: a backup written before the rename is exactly the one
    # somebody reaches for when an import went wrong on an upgrade.
    backups = sorted(
        (*backup_dir.glob(f"{BACKUP_PREFIX}*.sqlite"),
         *backup_dir.glob(f"{LEGACY_IMPORT_BACKUP_PREFIX}*.sqlite")),
        key=lambda p: (p.stat().st_mtime, p.name),
    )
    if not backups:
        raise FileNotFoundError("no backups to roll back to")
    latest = backups[-1]
    db.close()
    shutil.copy2(latest, db.path)
    return latest
