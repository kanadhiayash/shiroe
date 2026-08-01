"""Append-only JSONL atom store."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from shiroe.lock import MemoryLock, atomic_append, atomic_write
from shiroe.memory.schemas import ATOM_TYPES, STATUS_VALUES, AtomValidationError, validate_atom


ATOM_FILES = {
    "fact": "facts.jsonl",
    "decision": "decisions.jsonl",
    "risk": "risks.jsonl",
    "task": "tasks.jsonl",
    "preference": "preferences.jsonl",
    "contradiction": "contradictions.jsonl",
    "source": "sources.jsonl",
    "error": "errors.jsonl",
    "test": "tests.jsonl",
    "event": "events.jsonl",
    "constraint": "constraints.jsonl",
    "unknown": "unknowns.jsonl",
    "assumption": "assumptions.jsonl",
    "source_claim": "source_claims.jsonl",
    "route_policy": "route_policies.jsonl",
    "privacy_rule": "privacy_rules.jsonl",
    "handoff": "handoffs.jsonl",
}


class AtomStore:
    """Store memory atoms under `memory/l1_atoms/*.jsonl`."""

    def __init__(self, root: Path | str = Path(".")):
        self.root = Path(root)
        self.memory_dir = self.root / "memory"
        self.atom_dir = self.memory_dir / "l1_atoms"
        # Incremental dedup index: known atom ids + per-file byte offsets
        # already scanned. Appending atom N must not re-read the N-1 prior
        # atoms, so we only parse the bytes written since the last scan.
        self._known_ids: set[str] = set()
        self._scan_offsets: dict[Path, int] = {}

    def ensure_layout(self) -> None:
        """Create atom directory and empty type files."""
        self.atom_dir.mkdir(parents=True, exist_ok=True)
        for filename in ATOM_FILES.values():
            path = self.atom_dir / filename
            if not path.exists():
                path.write_text("", encoding="utf-8")

    def append(self, atom: dict[str, Any]) -> dict[str, Any]:
        """Validate and append an atom under the single-writer memory lock."""
        validate_atom(atom)
        self.ensure_layout()
        with MemoryLock(self.memory_dir):
            path = self._path_for_type(atom["type"])
            if atom["id"] in self._refresh_known_ids():
                raise AtomValidationError([f"duplicate atom id: {atom['id']}"])
            line = json.dumps(atom, sort_keys=True, separators=(",", ":")) + "\n"
            atomic_append(path, line)
            self._known_ids.add(atom["id"])
            self._scan_offsets[path] = self._scan_offsets.get(path, 0) + len(line.encode("utf-8"))
        return atom

    def load(
        self,
        *,
        atom_type: str | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        """Load atoms, optionally filtered by type and status."""
        if atom_type is not None and atom_type not in ATOM_TYPES:
            raise ValueError(f"invalid atom_type: {atom_type}")
        if status is not None and status not in STATUS_VALUES:
            raise ValueError(f"invalid status: {status}")

        paths = [self._path_for_type(atom_type)] if atom_type else self._atom_paths()
        atoms = list(self._read_paths(paths))
        if status is not None:
            atoms = [atom for atom in atoms if atom.get("status") == status]
        return atoms

    def get(self, atom_id: str) -> dict[str, Any] | None:
        """Return the first atom matching `atom_id`, or None."""
        for atom in self.load():
            if atom.get("id") == atom_id:
                return atom
        return None

    def patch(self, atom_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        """Patch one atom by rewriting only the owning JSONL file."""
        if "id" in updates and updates["id"] != atom_id:
            raise AtomValidationError(["atom id cannot be changed"])
        if "type" in updates:
            raise AtomValidationError(["atom type cannot be changed"])
        if "status" in updates and updates["status"] not in STATUS_VALUES:
            raise AtomValidationError([f"invalid status: {updates['status']}"])

        self.ensure_layout()
        with MemoryLock(self.memory_dir):
            for atom_type in sorted(ATOM_FILES):
                path = self._path_for_type(atom_type)
                atoms = list(self._read_paths([path]))
                for index, atom in enumerate(atoms):
                    if atom.get("id") != atom_id:
                        continue
                    patched = {**atom, **updates}
                    validate_atom(patched)
                    atoms[index] = patched
                    content = "".join(
                        json.dumps(item, sort_keys=True, separators=(",", ":")) + "\n"
                        for item in atoms
                    )
                    atomic_write(path, content)
                    # Rewrite invalidates the incremental scan offset. Ids are
                    # unchanged by patch and all of this file's atoms were just
                    # read, so record them and mark the file fully scanned.
                    self._known_ids.update(str(item["id"]) for item in atoms)
                    self._scan_offsets[path] = path.stat().st_size
                    return patched
        raise KeyError(atom_id)

    def _refresh_known_ids(self) -> set[str]:
        """Incrementally refresh the dedup id set. Call while holding the lock.

        Only bytes appended since the previous scan are parsed, so a run of
        N appends costs O(N) total instead of O(N^2). If a file changed in a
        non-append way (e.g. `patch` rewrote it), the tail parse fails or the
        file shrank; both trigger a full rescan of that file. Patches never
        change atom ids, so the id set itself stays correct either way.
        """
        for path in self._atom_paths():
            if not path.exists():
                self._scan_offsets.pop(path, None)
                continue
            size = path.stat().st_size
            offset = self._scan_offsets.get(path, 0)
            if size < offset:
                offset = 0
            if size == offset:
                continue
            with path.open("rb") as handle:
                handle.seek(offset)
                tail = handle.read()
            try:
                self._known_ids.update(self._ids_from_bytes(tail))
            except ValueError:
                # Mid-line offset after an out-of-band rewrite: rescan file.
                self._known_ids.update(self._ids_from_bytes(path.read_bytes()))
            self._scan_offsets[path] = size
        return self._known_ids

    @staticmethod
    def _ids_from_bytes(payload: bytes) -> list[str]:
        ids: list[str] = []
        for line in payload.decode("utf-8").splitlines():
            if not line.strip():
                continue
            atom = json.loads(line)
            if isinstance(atom, dict) and "id" in atom:
                ids.append(str(atom["id"]))
        return ids

    def _path_for_type(self, atom_type: str) -> Path:
        if atom_type not in ATOM_FILES:
            raise ValueError(f"invalid atom_type: {atom_type}")
        return self.atom_dir / ATOM_FILES[atom_type]

    def _atom_paths(self) -> list[Path]:
        return [self.atom_dir / ATOM_FILES[atom_type] for atom_type in sorted(ATOM_FILES)]

    def _read_paths(self, paths: Iterable[Path]) -> Iterable[dict[str, Any]]:
        for path in paths:
            if not path.exists():
                continue
            for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if not line.strip():
                    continue
                try:
                    atom = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise AtomValidationError([f"{path}:{line_number}: invalid JSONL ({exc})"]) from exc
                validate_atom(atom)
                yield atom
