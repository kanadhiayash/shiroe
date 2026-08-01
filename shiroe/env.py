"""Environment-variable reads, with the pre-rebrand names still honoured.

The Zeref -> Shiroe rebrand renamed every ``ZEREF_*`` variable to
``SHIROE_*``. Environment variables are an external contract: they live in
shell profiles, CI configs, and systemd units that this repo cannot reach and
cannot rewrite. Dropping the old names outright would not fail loudly -- an
unset variable simply falls back to its default, so a network guard would
silently re-arm and a configured lock timeout would silently revert.

So the new name wins, the old name still works, and using the old one emits a
DeprecationWarning naming its replacement.

# ponytail: fallback kept indefinitely for now; drop it in the release that
# follows a documented deprecation window, once SHIROE_* has been the
# documented spelling long enough for real setups to have moved.
"""

from __future__ import annotations

import os
import warnings

__all__ = ["getenv", "LEGACY_PREFIX", "PREFIX"]

PREFIX = "SHIROE_"
LEGACY_PREFIX = "ZEREF_"


def getenv(name: str, default: str | None = None) -> str | None:
    """Read ``SHIROE_<name>``, falling back to the deprecated ``ZEREF_<name>``.

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
