"""Environment-variable reads, with the pre-rebrand names still honoured.

The rename gave every variable the ``SHIROE_`` prefix. Environment variables
are an external contract: they live in shell profiles, CI configs, and systemd
units that this repo cannot reach and cannot rewrite. Dropping the old prefix
outright would not fail loudly -- an unset variable simply falls back to its
default, so a network guard would silently re-arm and a configured lock timeout
would silently revert.

So the new name wins, the old name still works, and using the old one emits a
DeprecationWarning naming its replacement. The old prefix itself is spelled
once, in :data:`shiroe.compat.legacy_identity.LEGACY_ENV_PREFIX`; its removal
plan is the row in ``docs/DEPRECATIONS.md``.
"""

from __future__ import annotations

import os
import warnings

from shiroe.compat.legacy_identity import LEGACY_ENV_PREFIX

__all__ = ["getenv", "LEGACY_PREFIX", "PREFIX"]

PREFIX = "SHIROE_"
LEGACY_PREFIX = LEGACY_ENV_PREFIX


def getenv(name: str, default: str | None = None) -> str | None:
    """Read ``SHIROE_<name>``, falling back to the deprecated legacy prefix.

    ``name`` is the suffix without a prefix, e.g. ``ALLOW_NETWORK``.
    """
    value = os.environ.get(PREFIX + name)
    if value is not None:
        return value
    legacy = os.environ.get(LEGACY_PREFIX + name)
    if legacy is not None:
        warnings.warn(
            f"{LEGACY_PREFIX}{name} is deprecated; use {PREFIX}{name}.",
            DeprecationWarning,
            stacklevel=2,
        )
        return legacy
    return default
