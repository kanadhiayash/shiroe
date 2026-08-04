"""SHIROE_* env vars, with the pre-rebrand prefix still honoured.

Environment variables live in shell profiles, CI configs, and systemd units
this repo cannot rewrite. Dropping the old prefix outright would not fail
loudly -- an unset variable falls back to its default, so a network guard
would silently re-arm and a configured lock timeout would silently revert.

The old prefix is spelled once, in shiroe/compat/legacy_identity.py, and read
from there here so this file pins the boundary rather than a copy of it.
"""

from __future__ import annotations

import warnings

import pytest

from shiroe.compat.legacy_identity import LEGACY_ENV_PREFIX
from shiroe.env import getenv
from shiroe.security.policy import _env_allow_network


def test_new_name_is_read(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SHIROE_ALLOW_NETWORK", "1")
    monkeypatch.delenv(LEGACY_ENV_PREFIX + "ALLOW_NETWORK", raising=False)
    assert getenv("ALLOW_NETWORK") == "1"


def test_legacy_name_still_works_and_warns(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SHIROE_ALLOW_NETWORK", raising=False)
    monkeypatch.setenv(LEGACY_ENV_PREFIX + "ALLOW_NETWORK", "1")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        assert getenv("ALLOW_NETWORK") == "1"
    assert any(issubclass(w.category, DeprecationWarning) for w in caught)
    assert any("SHIROE_ALLOW_NETWORK" in str(w.message) for w in caught)


def test_new_name_wins_when_both_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SHIROE_ALLOW_NETWORK", "0")
    monkeypatch.setenv(LEGACY_ENV_PREFIX + "ALLOW_NETWORK", "1")
    assert getenv("ALLOW_NETWORK") == "0"


def test_default_when_neither_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SHIROE_ALLOW_NETWORK", raising=False)
    monkeypatch.delenv(LEGACY_ENV_PREFIX + "ALLOW_NETWORK", raising=False)
    assert getenv("ALLOW_NETWORK", "fallback") == "fallback"


def test_legacy_name_still_opens_the_network_guard(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The end that matters: an operator whose CI still exports the old name
    keeps the behaviour they configured, rather than silently losing it."""
    monkeypatch.delenv("SHIROE_ALLOW_NETWORK", raising=False)
    monkeypatch.setenv(LEGACY_ENV_PREFIX + "ALLOW_NETWORK", "1")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        assert _env_allow_network() is True
