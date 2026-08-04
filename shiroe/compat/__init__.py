"""Compatibility boundary — the only package allowed to spell the old names.

The project shipped as Zeref before the rename (see ``MIGRATION.md``). A few
of those spellings are an external contract this repository cannot rewrite:
environment variables set in shell profiles, database files sitting in other
people's working trees, and a hand-maintained CSV that lives off-repo.

Every one of them is a named constant in :mod:`shiroe.compat.legacy_identity`
with an owner, a removal version, and a test. Runtime modules import from
there; none of them hardcodes a legacy string. ``docs/DEPRECATIONS.md`` is the
register, and ``tests/test_legacy_compatibility_boundary.py`` fails CI if an
alias is added without a row.
"""

from __future__ import annotations

__all__ = ["legacy_identity"]

from shiroe.compat import legacy_identity  # noqa: E402,F401
