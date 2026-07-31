"""SQLite index builder for memory atoms."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from shiroe.memory.atom_store import AtomStore


INDEX_PATH = Path("memory/indexes/shiroe.sqlite")
# Pre-rebrand cache filename. Purely derived from the JSONL atoms, so it is
# deleted rather than migrated -- rebuild_index regenerates it in full.
_LEGACY_INDEX_PATH = Path("memory/indexes/zeref.sqlite")


def rebuild_index(root: Path | str = Path(".")) -> dict[str, Any]:
    """Rebuild the SQLite cache from JSONL atoms."""
    root_path = Path(root)
    db_path = root_path / INDEX_PATH
    legacy = root_path / _LEGACY_INDEX_PATH
    if legacy.exists():
        legacy.unlink()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    atoms = AtomStore(root_path).load()

    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(
            """
            DROP TABLE IF EXISTS atoms;
            DROP TABLE IF EXISTS entities;
            DROP TABLE IF EXISTS links;
            DROP TABLE IF EXISTS events;
            DROP TABLE IF EXISTS atoms_fts;
            DROP TABLE IF EXISTS index_meta;

            CREATE TABLE index_meta(
              key TEXT PRIMARY KEY,
              value TEXT
            );

            CREATE TABLE atoms(
              id TEXT PRIMARY KEY,
              type TEXT,
              claim TEXT,
              summary TEXT,
              source TEXT,
              source_type TEXT,
              evidence TEXT,
              confidence TEXT,
              status TEXT,
              created_at TEXT,
              observed_at TEXT,
              last_confirmed_at TEXT,
              valid_from TEXT,
              valid_until TEXT,
              privacy TEXT,
              provenance TEXT,
              raw_json TEXT
            );

            CREATE TABLE entities(
              entity TEXT,
              atom_id TEXT,
              type TEXT,
              PRIMARY KEY(entity, atom_id)
            );

            CREATE TABLE links(
              source_id TEXT,
              target_id TEXT,
              relation TEXT,
              PRIMARY KEY(source_id, target_id, relation)
            );

            CREATE TABLE triples(
              subject TEXT,
              predicate TEXT,
              object TEXT,
              source_atom_id TEXT,
              confidence REAL,
              PRIMARY KEY(subject, predicate, object, source_atom_id)
            );

            CREATE TABLE events(
              id TEXT PRIMARY KEY,
              ts TEXT,
              event_type TEXT,
              payload TEXT
            );

            CREATE VIRTUAL TABLE atoms_fts USING fts5(
              id UNINDEXED,
              claim,
              summary,
              source,
              tags
            );
            """
        )
        # Records which tokenizer built this index, so search.py's
        # _index_stale() can detect a pre-upgrade index (built from raw text,
        # no bigrams) and fall back to the JSONL scan instead of silently
        # matching nothing against new query tokens.
        from shiroe.memory.search import TOKENIZER_VERSION  # local import: avoids a search<->indexer cycle

        conn.execute(
            "INSERT INTO index_meta(key, value) VALUES ('tokenizer_version', ?)",
            (str(TOKENIZER_VERSION),),
        )
        for atom in atoms:
            _insert_atom(conn, atom)
        conn.commit()
    finally:
        conn.close()

    return {"path": str(db_path), "atoms_indexed": len(atoms)}


def _insert_atom(conn: sqlite3.Connection, atom: dict[str, Any]) -> None:
    conn.execute(
        """
        INSERT INTO atoms(
          id, type, claim, summary, source, source_type, evidence, confidence,
          status, created_at, observed_at, last_confirmed_at, valid_from,
          valid_until, privacy, provenance, raw_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            atom["id"],
            atom["type"],
            atom["claim"],
            atom["summary"],
            atom["source"],
            atom["source_type"],
            atom["evidence"],
            atom["confidence"],
            atom["status"],
            atom["created_at"],
            atom["observed_at"],
            atom["last_confirmed_at"],
            atom["valid_from"],
            atom["valid_until"],
            atom["privacy"],
            atom["provenance"],
            json.dumps(atom, sort_keys=True),
        ),
    )
    # FTS5's default tokenizer treats a whole CJK run (no whitespace) as one
    # token, so a bigram query token would never equal it. Pre-tokenizing the
    # indexed text with the same tokenize() used for queries — including its
    # CJK bigram split — keeps index-time and query-time tokens symmetric for
    # every script, not just whitespace-delimited ones.
    from shiroe.memory.search import tokenize  # local import: avoids a search<->indexer cycle

    conn.execute(
        "INSERT INTO atoms_fts(id, claim, summary, source, tags) VALUES (?, ?, ?, ?, ?)",
        (
            atom["id"],
            " ".join(tokenize(atom["claim"])),
            " ".join(tokenize(atom["summary"])),
            " ".join(tokenize(atom["source"])),
            " ".join(tokenize(" ".join(str(tag) for tag in atom.get("tags", [])))),
        ),
    )
    for entity in atom.get("entities", []):
        if isinstance(entity, dict):
            name = str(entity.get("name", "")).strip()
            entity_type = str(entity.get("type", "unknown"))
        else:
            name = str(entity).strip()
            entity_type = "unknown"
        if name:
            conn.execute(
                "INSERT OR IGNORE INTO entities(entity, atom_id, type) VALUES (?, ?, ?)",
                (name, atom["id"], entity_type),
            )
    for link in atom.get("links", []):
        if isinstance(link, dict) and link.get("target_id"):
            conn.execute(
                "INSERT OR IGNORE INTO links(source_id, target_id, relation) VALUES (?, ?, ?)",
                (atom["id"], str(link["target_id"]), str(link.get("relation", "related"))),
            )

    # Deterministic, lexical-only extraction -- no model call, no NER. See
    # triples.py's module docstring for the precision-first guardrails.
    from shiroe.memory.triples import extract_triples  # local import: avoids a search<->indexer cycle

    for triple in extract_triples(atom):
        conn.execute(
            """
            INSERT OR IGNORE INTO triples(subject, predicate, object, source_atom_id, confidence)
            VALUES (?, ?, ?, ?, ?)
            """,
            (triple["subject"], triple["predicate"], triple["object"], triple["source_atom_id"], triple["confidence"]),
        )
