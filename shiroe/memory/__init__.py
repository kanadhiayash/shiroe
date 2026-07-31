"""Memory APIs for Shiroe.

This package preserves the existing Memory Core layout/write API while adding
the v2 atom schema and append-only JSONL store. Legacy Markdown files remain
human-readable views; atoms are the machine-facing source for new memory work.
"""

from shiroe.memory.atom_store import AtomStore
from shiroe.memory.core import (
    MEMORY_DIRS,
    MEMORY_FILES,
    MEMORY_LAYERS,
    PROJECT_DIRS,
    STATE_SCHEMA,
    MemoryLayout,
    MemoryRoot,
    MemoryWriter,
    discover_project_root,
    normalize_init_values,
    scaffold_project,
)
from shiroe.memory.schemas import (
    AtomValidationError,
    create_atom,
    make_atom_id,
    validate_atom,
)

__all__ = [
    "AtomStore",
    "AtomValidationError",
    "MEMORY_DIRS",
    "MEMORY_FILES",
    "MEMORY_LAYERS",
    "PROJECT_DIRS",
    "STATE_SCHEMA",
    "MemoryLayout",
    "MemoryRoot",
    "MemoryWriter",
    "create_atom",
    "discover_project_root",
    "make_atom_id",
    "normalize_init_values",
    "scaffold_project",
    "validate_atom",
]
