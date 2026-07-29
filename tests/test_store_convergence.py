"""Cross-store convergence: one logical fact lives in exactly one store.

Zeref accumulated three parallel fact stores — JSONL atoms
(``memory/l1_atoms/*.jsonl``), ``memory_cards`` in ``memory_state.py``, and
``memory_records`` in the vNext migrations — each written by a different
entry point. The stated architecture (docs/adr/ADR-0001) is one canonical
immutable history in JSONL, a derived current-state projection, and
generated Markdown. Nothing enforced that, so the stores drifted.

These tests are the enforcement. They are written to FAIL against the
pre-convergence layout and to keep failing if a fourth store is ever added,
which is the point: the guarantee has to be executable, not documented.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from zeref.guards.write_gate import propose_memory, write_from_proposal
from zeref.memory.atom_store import AtomStore
from zeref.memory_state import MemoryStore

CLAIM = "convergence probe: the deploy window is Tuesday 14:00 UTC"


@pytest.fixture()
def repo(fake_repo: Path) -> Path:
    """Reuses the shared `fake_repo` scaffold from tests/conftest.py."""
    return fake_repo


def _guarded_write(root: Path) -> dict:
    """Write one fact through the guarded pipeline — the path the CLI drives
    for `zeref memory propose` + `zeref memory write`.
    """
    proposal_path = root / "proposal.json"
    propose_memory(CLAIM, output=proposal_path)
    store = MemoryStore.from_root(root)
    return write_from_proposal(proposal_path, store)


def _atom_claims(root: Path) -> list[str]:
    return [atom.get("claim", "") for atom in AtomStore(root).load()]


def _card_claims(root: Path) -> list[str]:
    return [card.claim for card in MemoryStore.from_root(root).list_cards()]


def _record_claims(root: Path) -> list[str]:
    """Claims in the vNext ``memory_records`` table, or [] when that store is
    absent — its absence is the desired end state, not a test error.
    """
    db = root / "memory" / "state" / "zeref2.sqlite"
    if not db.exists():
        return []
    import sqlite3

    conn = sqlite3.connect(db)
    try:
        rows = conn.execute(
            "SELECT claim FROM sqlite_master "
            "JOIN memory_records WHERE sqlite_master.name = 'memory_records'"
        ).fetchall()
    except sqlite3.Error:
        return []
    finally:
        conn.close()
    return [row[0] for row in rows]


@pytest.mark.xfail(
    strict=True,
    reason=(
        "pre-convergence: the guarded write path still writes memory_cards "
        "instead of canonical JSONL atoms. strict=True means this flips to a "
        "build failure the moment convergence lands, forcing the marker off."
    ),
)
def test_guarded_write_lands_in_the_canonical_atom_store(repo: Path) -> None:
    """The guarded write path must write canonical history.

    Today it writes only to ``memory_cards``, so the JSONL atom store — the
    store the CLI's own `memory search` calls canonical, and the only one
    with bi-temporal support — never sees the fact at all.
    """
    _guarded_write(repo)
    assert CLAIM in _atom_claims(repo), (
        "guarded write did not reach the canonical JSONL atom store; "
        "it landed in a parallel store instead"
    )


@pytest.mark.xfail(
    strict=True,
    reason=(
        "pre-convergence: the guarded write path still writes memory_cards "
        "instead of canonical JSONL atoms. strict=True means this flips to a "
        "build failure the moment convergence lands, forcing the marker off."
    ),
)
def test_one_fact_is_not_duplicated_across_stores(repo: Path) -> None:
    """Exactly one store may hold a given logical fact.

    Writing the same claim into two stores is the drift itself: the two
    copies then age independently and nothing reconciles them.
    """
    _guarded_write(repo)
    holders = {
        name
        for name, claims in (
            ("jsonl_atoms", _atom_claims(repo)),
            ("memory_cards", _card_claims(repo)),
            ("memory_records", _record_claims(repo)),
        )
        if CLAIM in claims
    }
    assert holders == {"jsonl_atoms"}, (
        f"expected the claim in the canonical atom store only, found it in: "
        f"{sorted(holders) or 'no store at all'}"
    )


def test_markdown_views_are_generated_not_authored(repo: Path) -> None:
    """Markdown is a projection. Regenerating from history must be able to
    reproduce it, so exactly one generator may own ``memory/views/``.
    """
    from zeref.memory import render

    _guarded_write(repo)
    render.render_memory_view(repo, "all")
    views = repo / "memory" / "views"
    generated = sorted(p.name for p in views.glob("*.md")) if views.exists() else []
    assert generated, "no Markdown view was generated from canonical history"
    for name in generated:
        text = (views / name).read_text(encoding="utf-8")
        assert "generated" in text.lower(), (
            f"{name} carries no generated-file marker; a hand-authored file "
            f"in memory/views/ cannot be rebuilt from history"
        )


def test_only_one_sqlite_state_db_exists(repo: Path) -> None:
    """One derived current-state database, not three.

    ``memory/indexes/zeref.sqlite`` is the rebuildable index and is allowed.
    Two *state* databases under ``memory/state/`` means two schemas claiming
    to be current state.
    """
    _guarded_write(repo)
    state_dbs = sorted(p.name for p in (repo / "memory" / "state").glob("*.sqlite"))
    assert len(state_dbs) <= 1, (
        f"expected at most one canonical state database, found: {state_dbs}"
    )


@pytest.mark.xfail(
    strict=True,
    reason=(
        "pre-convergence: the guarded write path still writes memory_cards "
        "instead of canonical JSONL atoms. strict=True means this flips to a "
        "build failure the moment convergence lands, forcing the marker off."
    ),
)
def test_atom_history_is_append_only_json_lines(repo: Path) -> None:
    """Canonical history stays parseable line-by-line — this is what makes it
    the durable store the projections are rebuilt from.
    """
    _guarded_write(repo)
    atom_dir = repo / "memory" / "l1_atoms"
    files = sorted(atom_dir.glob("*.jsonl")) if atom_dir.exists() else []
    assert files, "no JSONL history files exist"
    for path in files:
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                json.loads(line)
            except json.JSONDecodeError as exc:
                pytest.fail(f"{path.name}:{lineno} is not valid JSON: {exc}")
