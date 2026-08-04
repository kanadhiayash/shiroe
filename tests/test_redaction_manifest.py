"""
SHR-029/031 — the history-redaction decision package is complete and honest.

`docs/security/HISTORY_REDACTION_MANIFEST.md` is the reviewable artifact the
owner reads before deciding whether this repository's history gets rewritten.
A manifest that is merely *present* is worth nothing; what makes it a decision
document is that every sensitive-data candidate found in the object store
carries exactly one of three verdicts, an owner who answers for it, and
evidence a reader can re-derive. This file is the gate on that.

Three things are checked, in increasing order of how much they can catch:

1. **Shape.** Every candidate carries a classification from the closed set, a
   named owner, and non-empty evidence. Nothing is unclassified.
2. **Coverage.** Every sensitive-pattern class known to the repo — those the
   history scanner looks for, and those `tests/test_no_private_operational_
   references.py` (SHR-022) guards the tree against — has at least one manifest
   row. Adding a new pattern class anywhere fails here until the manifest says
   what the new class's verdict is. That is the point: the manifest cannot go
   stale silently.
3. **Truth.** A row that claims `current-tree cleanup` is re-verified against
   the actual tree, using the SHR-022 scanner rather than trusting the prose.
   If the string is still there, the claim is a lie and this fails.

The manifest's machine-readable half lives in one tagged fenced JSON block, the
same convention `docs/canon/SOURCE_AUTHORITY.md` uses, so the prose around it
stays free to explain without the parser caring.

Nothing here executes anything the manifest names. `evidence.verify` is recorded
as a string for a human to run; a test that shelled out to strings lifted from a
document would be a code-execution path through a Markdown file.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from tests.test_no_private_operational_references import PATTERNS as TREE_GUARD_PATTERNS
from tests.test_no_private_operational_references import scan_tree

MANIFEST_REL = "docs/security/HISTORY_REDACTION_MANIFEST.md"
RUNBOOK_REL = "docs/security/HISTORY_REWRITE_RUNBOOK.md"
SCANNER_REL = "scripts/scan-history-sensitive.sh"

MANIFEST_SCHEMA = "shiroe.redaction-manifest/v1"

# The closed set. A verdict outside it is not a verdict.
CLASSIFICATIONS = {
    "current-tree cleanup",
    "all-history removal",
    "preserved historical lineage",
}

MANIFEST_BLOCK_RE = re.compile(
    r"```json\s+" + re.escape(MANIFEST_SCHEMA) + r"\s*\n(.*?)\n```",
    re.DOTALL,
)

# The scanner declares its pattern classes as `name|regex` rows inside one
# quoted block. Reading the names from the script keeps this test from carrying
# a second, drift-prone copy of the roster.
SCANNER_PATTERN_RE = re.compile(r"^(?P<name>[a-z][a-z0-9-]*)\|", re.MULTILINE)

# `paths` is checked separately: a pattern class with zero matching objects
# legitimately has none, and forcing a placeholder in would make the empty
# result indistinguishable from an unfilled row.
REQUIRED_EVIDENCE_KEYS = ("first_commit", "last_commit", "verify")


# --------------------------------------------------------------------------- #
# Loaders
# --------------------------------------------------------------------------- #

def _manifest(repo_root: Path) -> dict:
    path = repo_root / MANIFEST_REL
    assert path.exists(), f"{MANIFEST_REL} is missing — it is the deliverable"
    text = path.read_text(encoding="utf-8")
    match = MANIFEST_BLOCK_RE.search(text)
    assert match, (
        f"{MANIFEST_REL} carries no ```json {MANIFEST_SCHEMA} block; the "
        "machine-readable half of the manifest is what makes it auditable"
    )
    data = json.loads(match.group(1))
    assert data.get("schema") == MANIFEST_SCHEMA
    return data


def _candidates(repo_root: Path) -> list[dict]:
    candidates = _manifest(repo_root).get("candidates")
    assert isinstance(candidates, list) and candidates, (
        "manifest declares no candidates"
    )
    return candidates


def _scanner_pattern_classes(repo_root: Path) -> set[str]:
    path = repo_root / SCANNER_REL
    assert path.exists(), f"{SCANNER_REL} is missing — the scan must be re-runnable"
    return set(SCANNER_PATTERN_RE.findall(path.read_text(encoding="utf-8")))


# --------------------------------------------------------------------------- #
# 1. Shape — nothing is unclassified
# --------------------------------------------------------------------------- #

def test_every_candidate_has_a_classification_from_the_closed_set(repo_root: Path) -> None:
    bad = [
        (c.get("id"), c.get("classification"))
        for c in _candidates(repo_root)
        if c.get("classification") not in CLASSIFICATIONS
    ]
    assert not bad, (
        f"candidate(s) with a classification outside {sorted(CLASSIFICATIONS)}: "
        f"{bad}. Every candidate gets exactly one of the three verdicts."
    )


def test_every_candidate_has_an_owner_and_evidence(repo_root: Path) -> None:
    problems: list[str] = []
    for c in _candidates(repo_root):
        cid = c.get("id") or "<unnamed candidate>"
        if not str(c.get("owner") or "").strip():
            problems.append(f"{cid}: no owner")
        if not str(c.get("what") or "").strip():
            problems.append(f"{cid}: no description of what it is")
        if not str(c.get("blast_radius") or "").strip():
            problems.append(f"{cid}: no blast radius")
        if not str(c.get("rotation") or "").strip():
            problems.append(f"{cid}: no rotation status")
        if not isinstance(c.get("still_live"), bool):
            problems.append(f"{cid}: still_live is not a boolean")

        evidence = c.get("evidence")
        if not isinstance(evidence, dict):
            problems.append(f"{cid}: no evidence block")
            continue
        for key in REQUIRED_EVIDENCE_KEYS:
            value = evidence.get(key)
            if not value:
                problems.append(f"{cid}: evidence.{key} is empty")
        paths = evidence.get("paths")
        if not isinstance(paths, list):
            problems.append(f"{cid}: evidence.paths is not a list")
        elif not isinstance(evidence.get("objects"), int):
            problems.append(f"{cid}: evidence.objects is not an object count")
        elif evidence["objects"] > 0 and not paths:
            problems.append(
                f"{cid}: {evidence['objects']} matching object(s) but no paths — "
                "a finding with a count and no location is not evidence"
            )

    assert not problems, "incomplete candidate(s):\n  " + "\n  ".join(problems)


def test_candidate_ids_are_unique(repo_root: Path) -> None:
    ids = [c.get("id") for c in _candidates(repo_root)]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    assert not dupes, f"duplicate candidate id(s): {dupes}"


# --------------------------------------------------------------------------- #
# 2. Coverage — a new pattern class cannot appear without a verdict
# --------------------------------------------------------------------------- #

def test_every_scanner_pattern_class_has_a_manifest_row(repo_root: Path) -> None:
    declared = {c.get("pattern_class") for c in _candidates(repo_root)}
    missing = sorted(_scanner_pattern_classes(repo_root) - declared)
    assert not missing, (
        f"{SCANNER_REL} scans for pattern class(es) with no row in "
        f"{MANIFEST_REL}: {missing}. A class the scan looks for but the "
        "manifest never rules on is an unclassified candidate."
    )


def test_every_tree_guard_pattern_class_has_a_manifest_row(repo_root: Path) -> None:
    declared = {c.get("pattern_class") for c in _candidates(repo_root)}
    missing = sorted(set(TREE_GUARD_PATTERNS) - declared)
    assert not missing, (
        f"SHR-022 guards the tree against pattern class(es) that {MANIFEST_REL} "
        f"never rules on: {missing}. Adding a sensitive-pattern class to "
        "tests/test_no_private_operational_references.py requires a manifest row "
        "saying what history does with it."
    )


# --------------------------------------------------------------------------- #
# 3. Truth — a cleanup claim is re-verified, not taken on trust
# --------------------------------------------------------------------------- #

def test_current_tree_cleanup_claims_are_true(repo_root: Path) -> None:
    """A row saying the tree is clean is checked against the actual tree."""
    claimed_clean = {
        c["pattern_class"]
        for c in _candidates(repo_root)
        if c.get("classification") == "current-tree cleanup"
        and c.get("still_live") is False
        and c.get("pattern_class") in TREE_GUARD_PATTERNS
    }
    assert claimed_clean, (
        "no candidate claims a completed current-tree cleanup for any pattern "
        "class the SHR-022 guard can re-verify — the manifest is unfalsifiable"
    )

    live = [h for h in scan_tree(repo_root) if h.split(": ")[1] in claimed_clean]
    assert not live, (
        "manifest claims these classes are cleaned out of the current tree, but "
        "the SHR-022 scanner still finds them:\n  " + "\n  ".join(live)
    )


def test_all_history_removal_rows_are_not_claimed_resolved(repo_root: Path) -> None:
    """`all-history removal` is a *request*. It cannot be marked done here."""
    premature = [
        c.get("id")
        for c in _candidates(repo_root)
        if c.get("classification") == "all-history removal"
        and not str(c.get("approval") or "").strip()
    ]
    assert not premature, (
        f"all-history-removal candidate(s) with no `approval` field: {premature}. "
        "A rewrite request must name the approval it is still waiting on."
    )


# --------------------------------------------------------------------------- #
# The runbook and the scanner exist and say what they must
# --------------------------------------------------------------------------- #

def test_runbook_exists_and_states_the_approval_gate(repo_root: Path) -> None:
    path = repo_root / RUNBOOK_REL
    assert path.exists(), f"{RUNBOOK_REL} is missing"
    head = "\n".join(path.read_text(encoding="utf-8").splitlines()[:30]).lower()
    for phrase in ("written owner approval", "no step"):
        assert phrase in head, (
            f"{RUNBOOK_REL} must state the approval gate in its first 30 lines; "
            f"{phrase!r} not found"
        )


def test_runbook_names_the_manifest_version_it_gates_on(repo_root: Path) -> None:
    text = (repo_root / RUNBOOK_REL).read_text(encoding="utf-8")
    assert MANIFEST_REL in text, (
        f"{RUNBOOK_REL} must name {MANIFEST_REL} — approval is per manifest "
        "version, not blanket"
    )


@pytest.mark.parametrize("phrase", ["ref count", "object count"])
def test_scanner_reports_what_it_scanned(repo_root: Path, phrase: str) -> None:
    """The scan's output has to be auditable, not just a list of hits."""
    text = (repo_root / SCANNER_REL).read_text(encoding="utf-8").lower()
    assert phrase.replace(" ", "") in text.replace(" ", ""), (
        f"{SCANNER_REL} must report the {phrase} it covered so a reader can tell "
        "an empty result from an empty scan"
    )
