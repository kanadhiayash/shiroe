"""Architecture-reset invariants for vNext PR1 (ADR-0002).

Covers three families of guarantees:

1. Static repo scans — no leftover "faang-mangoes" council references in
   live surfaces, and no provider model ids leaked into the provider-neutral
   core package (``zeref/`` minus ``zeref/adapters/``).
2. Reasoning-class policy — criticality -> reasoning class resolution and
   the frontier/CRITICAL-only, no-upgrade rules in ``zeref.core.reasoning``.
3. Provider adapters, the deprecation alias shim, the registry contract,
   and loop-contract alias canonicalization.
"""

from __future__ import annotations

import json
import re
import warnings
from pathlib import Path

import pytest

import zeref.core.deprecations as deprecations
from zeref.core.deprecations import DEPRECATED_ALIASES, resolve_alias
from zeref.core.reasoning import (
    BALANCED,
    DEEP,
    FAST,
    FRONTIER,
    LOCAL,
    PRIVATE,
    ReasoningPolicyError,
    resolve_class,
    validate_request,
)
from zeref.adapters.providers import get_provider, resolve_model
from zeref.loops.contract import create_loop_contract

REPO_ROOT = Path(__file__).resolve().parents[1]

# Text/code surfaces that must never mention the retired "faang-mangoes"
# council. Historical references are allowed to live in CHANGELOG.md and
# docs/audits/ — neither of those is scanned here.
LIVE_SURFACES: tuple[str, ...] = (
    "zeref",
    "zeref-registry.json",
    "AGENTS.md",
    "SOUL.md",
    "agents",
    "commands",
    "team-packs",
    "skills",
    "config",
    "_shared",
    "docs/wiki",
)

BANNED_TERMS = ("mangoes", "faang-mangoes")

SKIP_SUFFIXES = (".pyc",)
SKIP_DIR_NAMES = {"__pycache__"}

PROVIDER_ID_PATTERN = re.compile(
    # Provider *model* ids only. Anthropic's models are `claude-<family><digit>`
    # (opus/sonnet/haiku/fable/instant); non-model tokens like `claude-obsidian`
    # (upstream project attribution in lineage) or `claude-code` (harness name)
    # are not model ids.
    r"claude-(?:opus|sonnet|haiku|fable|instant)"
    r"|gpt-[0-9]|gemini-[0-9]|codex-gpt"
)


def _iter_files(root: Path, path: Path):
    """Yield every file under ``path`` (relative to ``root``), skipping
    binary/cache noise. ``path`` may itself be a single file."""
    if path.is_file():
        yield path
        return
    if not path.exists():
        return
    for candidate in path.rglob("*"):
        if not candidate.is_file():
            continue
        if any(part in SKIP_DIR_NAMES for part in candidate.parts):
            continue
        if candidate.suffix in SKIP_SUFFIXES:
            continue
        yield candidate


def _readable_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return None


def test_no_council_references_in_live_surfaces() -> None:
    offenders: list[str] = []
    for surface in LIVE_SURFACES:
        surface_path = REPO_ROOT / surface
        for file_path in _iter_files(REPO_ROOT, surface_path):
            # No suffix filtering beyond SKIP_SUFFIXES: extensionless docs
            # and other text files are still worth scanning; anything
            # genuinely binary fails the UTF-8 decode in _readable_text
            # and is skipped there.
            text = _readable_text(file_path)
            if text is None:
                continue
            lowered = text.lower()
            for term in BANNED_TERMS:
                if term in lowered:
                    rel = file_path.relative_to(REPO_ROOT)
                    offenders.append(f"{rel}: contains {term!r}")

    assert not offenders, (
        "residual 'mangoes'/'faang-mangoes' references found in live surfaces "
        "(historical refs belong only in CHANGELOG.md, docs/audits/):\n"
        + "\n".join(sorted(offenders))
    )


def test_no_provider_model_ids_in_core_package() -> None:
    core_root = REPO_ROOT / "zeref"
    adapters_root = REPO_ROOT / "zeref" / "adapters"
    offenders: list[str] = []

    for file_path in core_root.rglob("*.py"):
        if any(part in SKIP_DIR_NAMES for part in file_path.parts):
            continue
        try:
            adapters_root_resolved = adapters_root.resolve()
            file_resolved = file_path.resolve()
        except OSError:
            continue
        if adapters_root_resolved in file_resolved.parents or file_resolved == adapters_root_resolved:
            continue

        text = _readable_text(file_path)
        if text is None:
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            match = PROVIDER_ID_PATTERN.search(line)
            if match:
                rel = file_path.relative_to(REPO_ROOT)
                offenders.append(f"{rel}:{lineno}: {match.group(0)!r} in {line.strip()!r}")

    assert not offenders, (
        "provider model ids leaked into core package (must live only in "
        "zeref/adapters/**):\n" + "\n".join(sorted(offenders))
    )


# --- reasoning class policy -------------------------------------------------


def test_resolve_class_criticality_map() -> None:
    assert resolve_class("LOW") == FAST
    assert resolve_class("MEDIUM") == BALANCED
    assert resolve_class("HIGH") == DEEP
    assert resolve_class("CRITICAL") == FRONTIER
    # case-insensitive
    assert resolve_class("low") == FAST

    with pytest.raises(ReasoningPolicyError):
        resolve_class("nonsense")


def test_frontier_is_critical_only() -> None:
    for criticality in ("HIGH", "MEDIUM", "LOW"):
        with pytest.raises(ReasoningPolicyError):
            validate_request(criticality, "frontier")
    assert validate_request("CRITICAL", "frontier") == "frontier"


def test_validate_request_downgrade_and_placement() -> None:
    # downgrades allowed
    assert validate_request("CRITICAL", "fast") == "fast"
    assert validate_request("HIGH", "balanced") == "balanced"

    # upgrades denied
    with pytest.raises(ReasoningPolicyError):
        validate_request("LOW", "balanced")
    with pytest.raises(ReasoningPolicyError):
        validate_request("MEDIUM", "deep")

    # placement classes allowed at any weight
    assert validate_request("LOW", "local") == LOCAL
    assert validate_request("LOW", "private") == PRIVATE

    # unknown class raises
    with pytest.raises(ReasoningPolicyError):
        validate_request("LOW", "nonsense")


# --- provider adapters -------------------------------------------------------


def test_anthropic_adapter_mapping() -> None:
    frontier = resolve_model("frontier", provider="anthropic")
    assert frontier.model_id == "claude-fable-5"
    assert frontier.effort == "high"

    deep = resolve_model("deep", provider="anthropic")
    assert deep.model_id == "claude-opus-4-8"

    balanced = resolve_model("balanced", provider="anthropic")
    assert balanced.model_id == "claude-sonnet-5"

    fast = resolve_model("fast", provider="anthropic")
    assert fast.model_id == "claude-haiku-4-5"

    with pytest.raises(ReasoningPolicyError):
        resolve_model("local", provider="anthropic")

    with pytest.raises(KeyError):
        get_provider("nonexistent")


def test_openai_adapter_fast() -> None:
    fast = resolve_model("fast", provider="openai")
    assert fast.model_id == "gpt-4o-mini"


# --- deprecation aliases ------------------------------------------------------


EXPECTED_ALIASES = {
    "small": "lean",
    "medium": "balanced",
    "enterprise": "assured",
    "skill-router": "capability-resolver",
    "fleet-activator": "capability-prober",
    "skill-importer": "capability-manager",
    "haiku": "fast",
    "sonnet": "balanced",
    "opus": "deep",
}


def test_deprecation_aliases() -> None:
    assert set(DEPRECATED_ALIASES) == set(EXPECTED_ALIASES)

    for old_name, new_name in EXPECTED_ALIASES.items():
        deprecations._warned.discard(old_name)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            result = resolve_alias(old_name)
        assert result == new_name
        assert any(issubclass(w.category, DeprecationWarning) for w in caught), (
            f"expected a DeprecationWarning resolving alias {old_name!r}"
        )

    # non-alias passes through unchanged
    assert resolve_alias("lean") == "lean"


# --- registry contract --------------------------------------------------------


def test_registry_reasoning_class_and_status() -> None:
    registry_path = REPO_ROOT / "zeref-registry.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))

    canonical_version = (REPO_ROOT / "zeref" / "VERSION").read_text(encoding="utf-8").strip()
    assert registry["version"] == canonical_version

    allowed_classes = {"fast", "balanced", "deep", "frontier"}
    allowed_statuses = {"runtime", "adapter", "contract", "experimental"}

    for skill in registry["skills"]:
        name = skill.get("skill")
        assert skill.get("reasoning_class") in allowed_classes, (
            f"skill {name!r} has invalid reasoning_class {skill.get('reasoning_class')!r}"
        )
        assert skill.get("status") in allowed_statuses, (
            f"skill {name!r} has invalid status {skill.get('status')!r}"
        )
        assert "model" not in skill, f"skill {name!r} still carries a 'model' key"
        assert "model_alias" not in skill, f"skill {name!r} still carries a 'model_alias' key"

    team_packs = registry["team_packs"]
    assert len(team_packs) == 9
    pack_names = {pack["pack"] for pack in team_packs}
    assert "faang-mangoes-council" not in pack_names

    for pack in team_packs:
        pack_path = REPO_ROOT / pack["path"]
        assert pack_path.exists(), f"team_pack {pack['pack']!r} path missing: {pack['path']}"


# --- loop contract -------------------------------------------------------------


def test_loop_contract_canonicalizes_team_alias(tmp_path: Path) -> None:
    deprecations._warned.discard("small")

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        contract = create_loop_contract(tmp_path, "goal x", team_pack="small")

    assert contract["team_pack"] == "lean"
    assert any(issubclass(w.category, DeprecationWarning) for w in caught)

    stored = json.loads((tmp_path / "memory" / "loops" / "latest.json").read_text(encoding="utf-8"))
    assert stored["team_pack"] == "lean"

    # default call also canonicalizes/stores "lean"
    default_contract = create_loop_contract(tmp_path, "goal y")
    assert default_contract["team_pack"] == "lean"
