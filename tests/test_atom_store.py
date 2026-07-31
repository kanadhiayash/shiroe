from __future__ import annotations

import json

import pytest

from shiroe.memory.atom_store import AtomStore
from shiroe.memory.schemas import AtomValidationError, create_atom


def _atom(claim: str = "Use atom JSONL before rendered markdown.") -> dict:
    return create_atom(
        atom_type="decision",
        claim=claim,
        summary="Machine-facing memory should be append-only atoms.",
        source="manual:test",
        source_type="manual",
        evidence="A",
        confidence="high",
        status="active",
        privacy="public-safe",
        provenance="unit-test",
        created_at="2026-07-09T10:00:00+00:00",
    )


def test_atom_store_appends_with_lock_and_loads_by_type_status(fake_repo) -> None:
    store = AtomStore(fake_repo)
    atom = store.append(_atom())

    path = fake_repo / "memory" / "l1_atoms" / "decisions.jsonl"
    assert path.exists()
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["id"] == atom["id"]

    assert store.load(atom_type="decision") == [atom]
    assert store.load(status="active") == [atom]
    assert store.load(status="archived") == []


def test_atom_store_rejects_duplicate_ids(fake_repo) -> None:
    store = AtomStore(fake_repo)
    atom = store.append(_atom())

    with pytest.raises(AtomValidationError) as exc:
        store.append(atom)

    assert "duplicate atom id" in str(exc.value)


def test_atom_store_patches_existing_atom_without_changing_type(fake_repo) -> None:
    store = AtomStore(fake_repo)
    atom = store.append(_atom())

    patched = store.patch(atom["id"], {"status": "superseded", "summary": "Superseded by newer decision."})

    assert patched["status"] == "superseded"
    assert patched["summary"] == "Superseded by newer decision."
    assert store.load(atom_type="decision", status="active") == []
    assert store.load(atom_type="decision", status="superseded") == [patched]


def test_atom_store_rejects_invalid_patch(fake_repo) -> None:
    store = AtomStore(fake_repo)
    atom = store.append(_atom())

    with pytest.raises(AtomValidationError) as exc:
        store.patch(atom["id"], {"type": "risk"})

    assert "atom type cannot be changed" in str(exc.value)


def test_atom_store_missing_patch_target_raises_key_error(fake_repo) -> None:
    store = AtomStore(fake_repo)

    with pytest.raises(KeyError):
        store.patch("decision_missing", {"status": "archived"})
