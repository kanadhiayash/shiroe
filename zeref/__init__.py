"""Zeref — reference Python runtime."""

from pathlib import Path

_VERSION_FILE = Path(__file__).resolve().parent / "VERSION"
try:
    __version__ = _VERSION_FILE.read_text(encoding="utf-8").strip()
except OSError:
    __version__ = "0.0.0+unknown"

__all__ = ["privacy", "cli", "core", "db", "memory", "memory_state", "__version__"]
