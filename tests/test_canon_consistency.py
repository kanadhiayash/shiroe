"""
Drives scripts/check-canon-consistency.py — the SHR-003..SHR-006 canon audit.

Two halves:

* Real-tree tests bind the audit to the actual checkout: the authority map must
  declare a total order, ADR-0001 must be the accepted authority for the
  canonical-store question, every baseline acknowledgement must be attributable,
  and the checker must exit clean.
* Synthetic-tree tests are the anti-vacuity proof. A checker that never fires is
  worthless, so each detector is fed a tmp_path repo with exactly one injected
  defect and must fail on it — and must stay silent when the same defect lives
  under an archived glob.

The script filename has hyphens and is not importable; it is driven via
subprocess, matching tests/test_validator.py and tests/test_version_consistency.py.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest


SCRIPT_REL = "scripts/check-canon-consistency.py"
AUTHORITY_REL = "docs/canon/SOURCE_AUTHORITY.md"
BASELINE_REL = "docs/canon/canon-baseline.json"
LEDGER_REL = "docs/canon/PUBLIC_CLAIM_LEDGER.json"

AUTHORITY_BLOCK_RE = re.compile(
    r"```json\s+shiroe\.source-authority/v1\s*\n(.*?)\n```",
    re.DOTALL,
)

# The five source classes SHR-003 names explicitly.
SHR003_REQUIRED_TIER_IDS = {
    "code-and-schemas",
    "accepted-adrs",
    "agents-spec",
    "glossary",
    "generated-docs",
}

# Contradictions this PR only *detects*. Each is (surface, rule, probe regex).
# Written as an implication: present on the surface => acknowledged in baseline.
# PR 02 removes the text; the assertion then passes vacuously instead of flipping red.
KNOWN_CONTRADICTIONS = [
    ("SOUL.md", "markdown-canonical", r"(?i)canonical[^.;\n]{0,60}\bmarkdown\b"),
    ("AGENTS.md", "markdown-canonical", r"(?i)canonical[^.;\n]{0,60}\bmarkdown\b"),
    ("AGENTS.md", "canonical-wiki", r"(?i)canonical\s+wiki"),
]


def _run(script: Path, root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script), "--root", str(root)],
        capture_output=True,
        text=True,
    )


def _authority_map(repo_root: Path) -> dict:
    text = (repo_root / AUTHORITY_REL).read_text(encoding="utf-8")
    blocks = AUTHORITY_BLOCK_RE.findall(text)
    assert len(blocks) == 1, (
        f"{AUTHORITY_REL} must carry exactly one "
        f"```json shiroe.source-authority/v1 block, found {len(blocks)}"
    )
    return json.loads(blocks[0])


# --------------------------------------------------------------------------- #
# Real tree
# --------------------------------------------------------------------------- #


def test_canon_script_exists(repo_root: Path) -> None:
    assert (repo_root / SCRIPT_REL).exists(), f"{SCRIPT_REL} is missing"


def test_canon_audit_exits_clean_on_real_tree(repo_root: Path) -> None:
    result = _run(repo_root / SCRIPT_REL, repo_root)
    assert result.returncode == 0, (
        f"canon audit failed (exit {result.returncode}):\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )


def test_authority_map_declares_a_total_order(repo_root: Path) -> None:
    amap = _authority_map(repo_root)
    ranks = [t["rank"] for t in amap["tiers"]]
    assert len(ranks) == len(set(ranks)), f"tier ranks are not unique: {ranks}"
    assert sorted(ranks) == list(range(1, len(ranks) + 1)), (
        f"tier ranks must be contiguous 1..N, got {sorted(ranks)}"
    )


def test_authority_map_covers_shr003_source_classes(repo_root: Path) -> None:
    amap = _authority_map(repo_root)
    ids = {t["id"] for t in amap["tiers"]}
    missing = SHR003_REQUIRED_TIER_IDS - ids
    assert not missing, f"authority map is missing SHR-003 source classes: {sorted(missing)}"


def test_authority_map_has_archived_and_unscoped_sections(repo_root: Path) -> None:
    amap = _authority_map(repo_root)
    assert amap["schema"] == "shiroe.source-authority/v1"
    assert amap["archived"], "authority map must name at least one archived surface"
    assert amap["unscoped"], "authority map must name the unscoped (non-canon) globs"


def test_adr_0001_is_the_accepted_canonical_store_authority(repo_root: Path) -> None:
    amap = _authority_map(repo_root)
    rules = {r["question"]: r for r in amap["conflict_rules"]}
    assert "canonical-store" in rules, "no conflict rule for the canonical-store question"
    authority = repo_root / rules["canonical-store"]["authority"]
    assert authority.exists(), f"conflict authority {authority} does not exist"
    assert "**Status:** Accepted" in authority.read_text(encoding="utf-8"), (
        f"{authority} is cited as an authority but is not Accepted"
    )


def test_every_baseline_acknowledgement_is_attributable(repo_root: Path) -> None:
    baseline = json.loads((repo_root / BASELINE_REL).read_text(encoding="utf-8"))
    seen: set[str] = set()
    for finding in baseline["findings"]:
        fid = finding["id"]
        assert fid not in seen, f"duplicate baseline finding id: {fid}"
        seen.add(fid)
        assert finding["status"] in {"acknowledged", "wontfix", "resolved"}
        if finding["status"] in {"acknowledged", "wontfix"}:
            for field in ("owner", "resolving_pr", "why_open"):
                assert finding.get(field), (
                    f"baseline finding {fid} is anonymous: missing {field!r}"
                )
        assert finding["shr"].startswith("SHR-")
        assert isinstance(finding["count"], int) and finding["count"] >= 1


@pytest.mark.parametrize("surface,rule,probe", KNOWN_CONTRADICTIONS)
def test_known_contradiction_is_absent_or_acknowledged(
    repo_root: Path, surface: str, rule: str, probe: str
) -> None:
    """Detect-only PR: if the text is still there it must be on the books."""
    text = (repo_root / surface).read_text(encoding="utf-8")
    if not re.search(probe, text):
        return  # PR 02 removed it — nothing to acknowledge.
    baseline = json.loads((repo_root / BASELINE_REL).read_text(encoding="utf-8"))
    ids = {f["id"] for f in baseline["findings"] if f["status"] != "resolved"}
    assert f"{surface}::{rule}" in ids, (
        f"{surface} still contains the {rule} contradiction but the baseline "
        f"does not acknowledge it"
    )


def test_public_claim_ledger_entries_are_well_formed(repo_root: Path) -> None:
    ledger = json.loads((repo_root / LEDGER_REL).read_text(encoding="utf-8"))
    assert ledger["schema"] == "shiroe.public-claim-ledger/v1"
    assert ledger["claims"], "ledger must carry at least one claim"
    seen: set[str] = set()
    for claim in ledger["claims"]:
        cid = claim["id"]
        assert cid not in seen, f"duplicate claim id: {cid}"
        seen.add(cid)
        assert claim["claim_class"] in {"machine_verified", "command_attested", "manual"}
        assert claim["status"] in {"verified", "unverified", "contradicted", "removed"}
        assert (repo_root / claim["surface"]).exists(), (
            f"claim {cid} names a surface that does not exist: {claim['surface']}"
        )
        assert (
            "verify" in claim or "evidence_command" in claim or "evidence_path" in claim
        ), f"claim {cid} carries no evidence handle"
        if claim["status"] != "verified":
            for field in ("owner", "resolving_pr", "why_unverified"):
                assert claim.get(field), (
                    f"non-verified claim {cid} is anonymous: missing {field!r}"
                )


def test_status_enum_is_single_sourced_from_the_schema(repo_root: Path) -> None:
    """SHR-005 labels live in the schema; nothing may hardcode them."""
    schema = json.loads(
        (repo_root / "registry" / "shiroe-registry.schema.json").read_text(encoding="utf-8")
    )
    skills_enum = schema["properties"]["skills"]["items"]["properties"]["status"]["enum"]
    agents_enum = schema["properties"]["agents"]["items"]["properties"]["status"]["enum"]
    assert skills_enum == agents_enum, (
        f"status enum diverges between skills {skills_enum} and agents {agents_enum}"
    )
    script = (repo_root / SCRIPT_REL).read_text(encoding="utf-8")
    for label in skills_enum:
        assert f'"{label}"' not in script, (
            f"status label {label!r} is hardcoded in {SCRIPT_REL}; "
            f"read it from the schema instead"
        )


# --------------------------------------------------------------------------- #
# Synthetic trees — the anti-vacuity proof
# --------------------------------------------------------------------------- #

_SYNTH_AUTHORITY_MAP = {
    "schema": "shiroe.source-authority/v1",
    "tiers": [
        {"rank": 1, "id": "code-and-schemas", "paths": ["registry/*.schema.json"]},
        {"rank": 2, "id": "accepted-adrs", "paths": ["docs/adr/ADR-*.md"]},
        {"rank": 3, "id": "agents-spec", "paths": ["AGENTS.md"]},
        {"rank": 4, "id": "glossary", "paths": ["docs/GLOSSARY.md"]},
        {"rank": 5, "id": "generated-docs", "paths": ["shiroe-registry.json"]},
        {"rank": 6, "id": "narrative-docs", "paths": ["README.md", "docs/notes/*.md"]},
    ],
    "archived": [
        {"id": "old-canon", "paths": ["references/old/**"], "marker": "Superseded"},
    ],
    "unscoped": ["docs/canon/**"],
    "conflict_rules": [
        {
            "question": "canonical-store",
            "authority": "docs/adr/ADR-0001-canonical-store.md",
            "resolution": "sqlite=current-state, jsonl=history, markdown=generated-view",
        }
    ],
}

_SYNTH_SCHEMA = {
    "properties": {
        "skills": {
            "items": {
                "properties": {
                    "status": {"type": "string", "enum": ["runtime", "adapter", "contract", "experimental"]}
                }
            }
        },
        "agents": {
            "items": {
                "properties": {
                    "status": {"type": "string", "enum": ["runtime", "adapter", "contract", "experimental"]}
                }
            }
        },
    }
}

_SYNTH_REGISTRY = {
    "version": "0.0.0",
    "skills": [{"id": "s1", "status": "runtime"}],
    "agents": [{"id": "a1", "status": "contract"}],
    "commands": [{"id": "c1", "status": "runtime"}],
    "team_packs": [{"id": "t1", "status": "contract"}],
    "gates": [{"id": "g1", "status": "runtime"}],
}

_SYNTH_LEDGER = {
    "schema": "shiroe.public-claim-ledger/v1",
    "verified_at_commit": None,
    "claims": [
        {
            "id": "synth-notes-count",
            "surface": "README.md",
            "line": 3,
            "claim": "1 files of notes",
            "claim_class": "machine_verified",
            "status": "verified",
            "evidence_value": 1,
            "verify": {"kind": "count_glob", "glob": "docs/notes/*.md"},
        }
    ],
}

_SYNTH_BASELINE = {
    "schema": "shiroe.canon-baseline/v1",
    "generated": "2026-08-03",
    "recorded_at_commit": None,
    "findings": [],
}


def _synth(tmp_path: Path, **overrides: str | None) -> Path:
    """
    Minimum viable synthetic root: every file classified, zero findings.

    `overrides` maps a repo-relative path to file content; a value of None
    deletes the file. JSON structures are injected by writing the path directly.
    """
    root = tmp_path / "synth"
    files: dict[str, str] = {
        "README.md": "# Synth\n\nSQLite is canonical for current state.\n1 files of notes.\n",
        "AGENTS.md": "# AGENTS\n\nSpec surface.\n",
        "docs/GLOSSARY.md": "# Glossary\n\nCanonical store invariant.\n",
        "docs/notes/note.md": "# Note\n\nNothing controversial here.\n",
        "docs/adr/ADR-0001-canonical-store.md": (
            "# ADR-0001\n\n**Status:** Accepted\n\nSQLite is the canonical current state.\n"
        ),
        "references/old/legacy.md": "# Legacy\n\nSuperseded by ADR-0001.\n",
        "registry/shiroe-registry.schema.json": json.dumps(_SYNTH_SCHEMA, indent=2),
        "shiroe-registry.json": json.dumps(_SYNTH_REGISTRY, indent=2),
        AUTHORITY_REL: (
            "# Source authority\n\nPrecedence, highest first.\n\n"
            "```json shiroe.source-authority/v1\n"
            + json.dumps(_SYNTH_AUTHORITY_MAP, indent=2)
            + "\n```\n"
        ),
        BASELINE_REL: json.dumps(_SYNTH_BASELINE, indent=2),
        LEDGER_REL: json.dumps(_SYNTH_LEDGER, indent=2),
    }
    files.update(overrides)  # type: ignore[arg-type]

    for rel, content in files.items():
        path = root / rel
        if content is None:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return root


def _baseline_with(*findings: dict) -> str:
    return json.dumps({**_SYNTH_BASELINE, "findings": list(findings)}, indent=2)


CONTRADICTION_LINE = "Canonical state is markdown on disk.\n"


def test_clean_synthetic_tree_passes(repo_root: Path, tmp_path: Path) -> None:
    result = _run(repo_root / SCRIPT_REL, _synth(tmp_path))
    assert result.returncode == 0, (
        f"clean synthetic tree should pass:\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )


def test_injected_contradiction_fails(repo_root: Path, tmp_path: Path) -> None:
    root = _synth(
        tmp_path,
        **{"docs/notes/bad.md": "# Bad\n\n" + CONTRADICTION_LINE},
    )
    result = _run(repo_root / SCRIPT_REL, root)
    assert result.returncode == 1, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    assert "NEW:" in result.stderr, result.stderr
    assert "bad.md" in result.stderr, result.stderr


def test_archived_path_is_not_scanned(repo_root: Path, tmp_path: Path) -> None:
    """Same contradicting sentence, but under an archived glob — must stay silent."""
    root = _synth(
        tmp_path,
        **{"references/old/legacy.md": "# Legacy\n\nSuperseded by ADR-0001.\n" + CONTRADICTION_LINE},
    )
    result = _run(repo_root / SCRIPT_REL, root)
    assert result.returncode == 0, (
        f"archived surfaces must not be scanned:\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )


def test_dropped_acknowledgement_fails(repo_root: Path, tmp_path: Path) -> None:
    root = _synth(
        tmp_path,
        **{
            BASELINE_REL: _baseline_with(
                {
                    "id": "docs/notes/ghost.md::markdown-canonical",
                    "shr": "SHR-004",
                    "count": 1,
                    "excerpt": "Canonical state is markdown on disk.",
                    "why_open": "placeholder",
                    "owner": "kanadhiayash",
                    "resolving_pr": "fix/shr-canonical-state",
                    "status": "acknowledged",
                }
            )
        },
    )
    result = _run(repo_root / SCRIPT_REL, root)
    assert result.returncode == 1, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    assert "DROPPED" in result.stderr, result.stderr


def test_count_drift_fails(repo_root: Path, tmp_path: Path) -> None:
    root = _synth(
        tmp_path,
        **{
            "docs/notes/bad.md": "# Bad\n\n" + CONTRADICTION_LINE + "\n" + CONTRADICTION_LINE,
            BASELINE_REL: _baseline_with(
                {
                    "id": "docs/notes/bad.md::markdown-canonical",
                    "shr": "SHR-004",
                    "count": 1,  # observed will be 2
                    "excerpt": "Canonical state is markdown on disk.",
                    "why_open": "placeholder",
                    "owner": "kanadhiayash",
                    "resolving_pr": "fix/shr-canonical-state",
                    "status": "acknowledged",
                }
            ),
        },
    )
    result = _run(repo_root / SCRIPT_REL, root)
    assert result.returncode == 1, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    assert "COUNT DRIFT" in result.stderr, result.stderr


def test_unclassified_surface_fails(repo_root: Path, tmp_path: Path) -> None:
    root = _synth(tmp_path, **{"stray/unknown.txt": "not claimed by any glob\n"})
    result = _run(repo_root / SCRIPT_REL, root)
    assert result.returncode == 1, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    assert "unclassified" in result.stderr.lower(), result.stderr


def test_missing_authority_map_exits_2(repo_root: Path, tmp_path: Path) -> None:
    root = _synth(tmp_path)
    (root / AUTHORITY_REL).unlink()
    result = _run(repo_root / SCRIPT_REL, root)
    assert result.returncode == 2, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"


def test_acknowledgement_without_owner_exits_2(repo_root: Path, tmp_path: Path) -> None:
    root = _synth(
        tmp_path,
        **{
            "docs/notes/bad.md": "# Bad\n\n" + CONTRADICTION_LINE,
            BASELINE_REL: _baseline_with(
                {
                    "id": "docs/notes/bad.md::markdown-canonical",
                    "shr": "SHR-004",
                    "count": 1,
                    "excerpt": "Canonical state is markdown on disk.",
                    "why_open": "placeholder",
                    # owner + resolving_pr deliberately absent
                    "status": "acknowledged",
                }
            ),
        },
    )
    result = _run(repo_root / SCRIPT_REL, root)
    assert result.returncode == 2, (
        f"anonymous acknowledgement must exit 2:\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )


def test_unledgered_numeric_claim_fails(repo_root: Path, tmp_path: Path) -> None:
    root = _synth(
        tmp_path,
        **{"README.md": "# Synth\n\n1 files of notes.\n\nWe run 500 tests on every push.\n"},
    )
    result = _run(repo_root / SCRIPT_REL, root)
    assert result.returncode == 1, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    assert "unledgered-claim" in result.stderr, result.stderr
