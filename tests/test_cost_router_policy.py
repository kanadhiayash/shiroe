"""SHR-63: route_operation() ordering and audit_budgets() mapping coverage.

Three defects in the pre-fix `route_operation`:
  1. It normalized `operation` to hyphen-spelling for dispatch but tested the
     RAW (underscore-spelled) `operation` against `forbidden_by_default`, so
     the hyphen spelling of a forbidden op walked straight past the deny.
  2. Operation-specific branches (memory-add, patch, ...) returned before
     the budget check, so an oversized memory-add still returned
     "atom-append" instead of being escalated.
  3. An unrecognized operation fell through to a "no-write" decision —
     failing open, silently, as though nothing needed doing.

And one defect in `audit_budgets()`: 7 of the 8 declared `artifact_budgets`
had no entry in the path-mapping dict and were silently `continue`-d past,
so a declared-but-unenforced budget read as enforced.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from shiroe.memory.cost_router import DEFAULT_POLICY, audit_budgets, route_operation

FORBIDDEN_OPS = DEFAULT_POLICY["forbidden_by_default"]

# Every dispatchable operation family, with an underscore and a hyphen
# spelling, so canonicalization is exercised on both sides (not just the
# forbidden list).
DISPATCH_ALIASES = [
    ("memory_add", "atom-append"),
    ("memory-add", "atom-append"),
    ("atom_append", "atom-append"),
    ("patch", "atom-patch"),
    ("metadata_update", "atom-patch"),
    ("atom-patch", "atom-patch"),
    ("render", "view-render"),
    ("view_render", "view-render"),
]


# ---------------------------------------------------------------------------
# Alias matrix — defect 1
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("forbidden_op", FORBIDDEN_OPS)
def test_forbidden_op_blocked_in_underscore_spelling(forbidden_op: str) -> None:
    result = route_operation(forbidden_op)
    assert result["executor"] == "blocked"
    assert result["reason"] == "operation forbidden by default"


@pytest.mark.parametrize("forbidden_op", FORBIDDEN_OPS)
def test_forbidden_op_blocked_in_hyphen_spelling(forbidden_op: str) -> None:
    hyphenated = forbidden_op.replace("_", "-")
    result = route_operation(hyphenated)
    assert result["executor"] == "blocked"
    assert result["reason"] == "operation forbidden by default"


@pytest.mark.parametrize("operation,expected_step", DISPATCH_ALIASES)
def test_dispatch_operation_aliases_canonicalize_the_same_way(operation: str, expected_step: str) -> None:
    result = route_operation(operation, text="short note")
    assert result["ladder_step"] == expected_step


# ---------------------------------------------------------------------------
# Precedence matrix — defect 2: global deny + budget run before dispatch
# ---------------------------------------------------------------------------

OVERSIZED_TEXT = "word " * 5000  # well past max_context_tokens_for_memory_write


def test_oversized_memory_add_is_escalated_not_atom_appended() -> None:
    """The named regression: previously returned atom-append regardless of size."""
    result = route_operation("memory-add", text=OVERSIZED_TEXT)
    assert result["ladder_step"] == "flagship-review"
    assert result["executor"] != "deterministic"
    assert result["reason"] == "input exceeds memory write budget"


@pytest.mark.parametrize(
    "operation,kwargs",
    [
        ("memory-add", {"duplicate": True}),
        ("patch", {"status_change": True}),
        ("render", {}),
        ("markdown-rewrite", {"approval": True}),
    ],
)
def test_budget_check_preempts_every_dispatch_family_when_oversized(operation: str, kwargs: dict) -> None:
    result = route_operation(operation, text=OVERSIZED_TEXT, **kwargs)
    assert result["ladder_step"] == "flagship-review"
    assert result["reason"] == "input exceeds memory write budget"


def test_forbidden_deny_beats_dispatch_flags() -> None:
    """A forbidden op stays blocked even if it also carries dispatch flags
    that would otherwise route it to a cheap deterministic step."""
    result = route_operation(FORBIDDEN_OPS[0], duplicate=True, status_change=True)
    assert result["executor"] == "blocked"
    assert result["reason"] == "operation forbidden by default"


def test_public_claim_beats_duplicate_dispatch() -> None:
    result = route_operation("memory-add", duplicate=True, public_claim=True)
    assert result["executor"] == "flagship"
    assert result["ladder_step"] == "flagship-review"


def test_small_memory_add_still_dispatches_normally() -> None:
    """Sanity check: the reordering must not block legitimate small writes."""
    result = route_operation("memory-add", text="short note")
    assert result["executor"] == "deterministic"
    assert result["ladder_step"] == "atom-append"


# ---------------------------------------------------------------------------
# Unknown operations fail closed — defect 3
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("operation", ["totally-made-up-operation", "", "some-view", "  "])
def test_unknown_operation_fails_closed(operation: str) -> None:
    result = route_operation(operation, text="hello")
    assert result["executor"] == "blocked"
    assert result["ladder_step"] != "no-write"
    assert "unknown operation" in result["reason"]


# ---------------------------------------------------------------------------
# audit_budgets: every declared budget mapped or explicitly failing
# ---------------------------------------------------------------------------


def test_every_declared_budget_is_mapped_or_fails_no_silent_skip(tmp_path: Path) -> None:
    memory = tmp_path / "memory"
    memory.mkdir()
    (memory / "hot.md").write_text("short and within budget", encoding="utf-8")

    result = audit_budgets(tmp_path)

    declared = set(DEFAULT_POLICY["artifact_budgets"])
    checked = {check["artifact"] for check in result["checks"]}
    assert checked == declared, "every declared budget must appear in checks — no silent skip"

    by_name = {check["artifact"]: check for check in result["checks"]}
    assert by_name["hot.md"]["ok"] is True

    unmapped = declared - {"hot.md"}
    for name in unmapped:
        assert by_name[name]["ok"] is False, f"{name} has no locator and must fail validation, not pass silently"

    assert result["passed"] is False
