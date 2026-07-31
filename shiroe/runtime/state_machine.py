"""RUN + STEP state machines (vNext §10.1, §10.2)."""

from __future__ import annotations


RUN_STATES = (
    "CREATED", "COMPILED", "AUTHORIZED", "RUNNING", "VERIFYING",
    "COMPLETED",
    "PAUSED_PERMISSION", "PAUSED_BUDGET", "RETRYING", "DEGRADED",
    "FAILED", "CANCELLED",
)

STEP_STATES = (
    "PENDING", "READY", "RUNNING", "OUTPUT_RECEIVED", "VALIDATING",
    "PASSED",
    "TIMED_OUT", "RETRYABLE_FAILURE", "PERMISSION_DENIED",
    "INVALID_OUTPUT", "FAILED", "SKIPPED",
)


_RUN_TRANSITIONS: dict[str, frozenset[str]] = {
    "CREATED":            frozenset({"COMPILED", "CANCELLED"}),
    "COMPILED":           frozenset({"AUTHORIZED", "CANCELLED"}),
    "AUTHORIZED":         frozenset({"RUNNING", "PAUSED_PERMISSION",
                                     "PAUSED_BUDGET", "CANCELLED"}),
    "RUNNING":            frozenset({"VERIFYING", "PAUSED_PERMISSION",
                                     "PAUSED_BUDGET", "RETRYING",
                                     "DEGRADED", "FAILED", "CANCELLED"}),
    "VERIFYING":          frozenset({"COMPLETED", "RUNNING", "FAILED",
                                     "DEGRADED", "CANCELLED"}),
    "PAUSED_PERMISSION":  frozenset({"RUNNING", "CANCELLED"}),
    "PAUSED_BUDGET":      frozenset({"RUNNING", "CANCELLED"}),
    "RETRYING":           frozenset({"RUNNING", "FAILED", "CANCELLED"}),
    "DEGRADED":           frozenset({"RUNNING", "FAILED", "CANCELLED"}),
    "COMPLETED":          frozenset(),
    "FAILED":             frozenset(),
    "CANCELLED":          frozenset(),
}


_STEP_TRANSITIONS: dict[str, frozenset[str]] = {
    "PENDING":            frozenset({"READY", "SKIPPED"}),
    "READY":              frozenset({"RUNNING", "SKIPPED"}),
    "RUNNING":            frozenset({"OUTPUT_RECEIVED", "TIMED_OUT",
                                     "RETRYABLE_FAILURE",
                                     "PERMISSION_DENIED", "FAILED"}),
    "OUTPUT_RECEIVED":    frozenset({"VALIDATING", "FAILED"}),
    "VALIDATING":         frozenset({"PASSED", "INVALID_OUTPUT", "FAILED"}),
    "TIMED_OUT":          frozenset({"RETRYABLE_FAILURE", "FAILED"}),
    "RETRYABLE_FAILURE":  frozenset({"READY", "FAILED"}),
    "PERMISSION_DENIED":  frozenset({"READY", "FAILED", "SKIPPED"}),
    "INVALID_OUTPUT":     frozenset({"RETRYABLE_FAILURE", "FAILED"}),
    "PASSED":             frozenset(),
    "FAILED":             frozenset(),
    "SKIPPED":            frozenset(),
}


class INVALID_RUN_TRANSITION(ValueError):  # noqa: N801 — exported as class
    pass


class INVALID_STEP_TRANSITION(ValueError):  # noqa: N801
    pass


def can_run_transition(current: str, target: str) -> bool:
    return target in _RUN_TRANSITIONS.get(current, frozenset())


def can_step_transition(current: str, target: str) -> bool:
    return target in _STEP_TRANSITIONS.get(current, frozenset())


def assert_run_transition(current: str, target: str) -> None:
    if not can_run_transition(current, target):
        raise INVALID_RUN_TRANSITION(
            f"invalid RUN transition {current!r} → {target!r}"
        )


def assert_step_transition(current: str, target: str) -> None:
    if not can_step_transition(current, target):
        raise INVALID_STEP_TRANSITION(
            f"invalid STEP transition {current!r} → {target!r}"
        )


# Steps that produce irreversible side effects must not be re-run on
# resume. The supervisor treats these terminal-succeeded states as
# "already done" — recovery.py picks the first non-terminal-succeeded step.
IRREVERSIBLE_TERMINAL_STEP_STATES: frozenset[str] = frozenset({
    "PASSED", "SKIPPED",
})
