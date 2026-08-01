"""SHR-61: deterministic criticality classifier for the routing gateway.

The entitlement table (:mod:`shiroe.core.reasoning`) is only as safe as the
criticality label it is fed. Before this module, that label was whatever the
caller typed — a caller that under-labels a dangerous task gets cheap
routing, and the entitlement table has no way to notice. This module scores
STRUCTURED SIGNALS about a task (reversibility, blast radius, privacy class,
etc.) instead of pattern-matching free text, so a task cannot talk its way
into a lower label just by being worded gently.

FAIL UPWARD is the load-bearing property, enforced structurally rather than
by convention: every signal below maps to a *floor* criticality, and the
result is the MAX of every floor that fires (see ``_LEVEL_ORDER`` / the
``_bump`` helper in ``classify``). There is no averaging and no signal can
pull the result down once another signal has raised it. Under-routing a
CRITICAL task is the expensive failure (it ships dangerous work on cheap,
shallow reasoning); over-routing a LOW task to HIGH only costs money. When
signals conflict, taking the max is the correct bias, not a compromise.

Placement (local/private execution) and privacy class are deliberately NOT
inputs to blast radius or reversibility judgements about *what* the task
does — they are scored on their own (privacy_class below) but a task that
merely runs locally does not become less critical for it. See
``shiroe.routing.gateway`` for the placement/reasoning-class orthogonality
this preserves.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from shiroe.core.reasoning import CRITICALITIES

# Ordered cheapest -> most expensive; index comparison is how "fail upward"
# (take the max) is implemented below.
_LEVEL_ORDER: tuple[str, ...] = CRITICALITIES  # ("LOW", "MEDIUM", "HIGH", "CRITICAL")

BLAST_RADII: tuple[str, ...] = ("local", "team", "org", "public")
PRIVACY_CLASSES: tuple[str, ...] = ("public", "internal", "confidential", "restricted")

# Grading vocabularies. In every one of these the FIRST value is the most
# severe, and it is also the field's default. That is deliberate and is the
# property `test_no_new_field_value_can_exceed_its_default` proves
# exhaustively: a caller who has never heard of these fields gets exactly the
# classification they would have got before the fields existed, and no value
# they can supply raises the result above that. Grading here only ever buys
# precision on tasks that are genuinely tamer — it never lowers a floor that
# was protecting something dangerous.
ENVIRONMENTS: tuple[str, ...] = ("production", "staging", "development")
CHANGE_SHAPES: tuple[str, ...] = ("breaking", "additive")
CLAIM_DIRECTIONS: tuple[str, ...] = ("asserting", "corrective")
FINANCIAL_EFFECTS: tuple[str, ...] = ("executes", "touches_path")


@dataclass(frozen=True)
class TaskSignals:
    """Structured description of a task, scored by :func:`classify`.

    No free-text field is scored. ``description`` exists purely for humans
    reading a corpus entry or an audit log; changing its wording can never
    change the classification, which is the point.
    """

    reversible: bool = True
    blast_radius: str = "local"  # local | team | org | public
    privacy_class: str = "internal"  # public | internal | confidential | restricted
    is_public_claim: bool = False
    schema_or_migration: bool = False
    production_or_credential_access: bool = False
    financial_or_legal_impact: bool = False
    writes_canonical_state: bool = False
    # Caller/analyst-declared: the signals above are incomplete or pull in
    # different directions. The classifier does not guess at ambiguity it
    # cannot see from booleans and enums — this is how a human says "I'm not
    # sure" and gets routed to human approval instead of silent auto-routing.
    # ponytail: explicit flag, not inferred ambiguity-detection; upgrade to
    # a sensitivity analysis over flipped signals if false negatives show up.
    ambiguous: bool = False
    # Grading dimensions. Defaults are the most severe value of each, so
    # omitting them reproduces the pre-grading classification exactly.
    environment: str = "production"  # production | staging | development
    change_shape: str = "breaking"  # breaking | additive
    claim_direction: str = "asserting"  # asserting | corrective
    financial_effect: str = "executes"  # executes | touches_path

    def __post_init__(self) -> None:
        if self.blast_radius not in BLAST_RADII:
            raise ValueError(f"unknown blast_radius {self.blast_radius!r}; expected one of {BLAST_RADII}")
        if self.privacy_class not in PRIVACY_CLASSES:
            raise ValueError(f"unknown privacy_class {self.privacy_class!r}; expected one of {PRIVACY_CLASSES}")
        if self.environment not in ENVIRONMENTS:
            raise ValueError(f"unknown environment {self.environment!r}; expected one of {ENVIRONMENTS}")
        if self.change_shape not in CHANGE_SHAPES:
            raise ValueError(f"unknown change_shape {self.change_shape!r}; expected one of {CHANGE_SHAPES}")
        if self.claim_direction not in CLAIM_DIRECTIONS:
            raise ValueError(f"unknown claim_direction {self.claim_direction!r}; expected one of {CLAIM_DIRECTIONS}")
        if self.financial_effect not in FINANCIAL_EFFECTS:
            raise ValueError(f"unknown financial_effect {self.financial_effect!r}; expected one of {FINANCIAL_EFFECTS}")


@dataclass(frozen=True)
class Classification:
    """Result of scoring a :class:`TaskSignals`."""

    criticality: str
    rationale: str
    flagged_for_review: bool
    reasons: tuple[str, ...] = field(default_factory=tuple)


def _bump(current: str, candidate: str) -> str:
    """Fail upward: never let a later signal pull the level back down."""
    if _LEVEL_ORDER.index(candidate) > _LEVEL_ORDER.index(current):
        return candidate
    return current


def classify(signals: TaskSignals) -> Classification:
    """Score ``signals`` to a criticality, biased to over- rather than under-classify.

    Each rule below states the floor it forces and why. The final level is
    the max over every rule that fires — a single hard trigger is enough to
    reach CRITICAL even if every other signal looks tame.
    """
    level = "LOW"
    reasons: list[str] = []

    def bump(candidate: str, reason: str) -> None:
        nonlocal level
        level = _bump(level, candidate)
        reasons.append(f"{reason} -> floor {candidate}")

    # --- hard CRITICAL triggers: each is independently sufficient ----------
    # A public claim is graded by DIRECTION. Publishing a new claim exposes
    # the project to something it cannot take back; withdrawing an overstated
    # one moves the exposure the other way. Treating both as CRITICAL made
    # correcting an inaccurate claim as expensive as making one, which
    # discourages exactly the behaviour that should be cheap. An irretractable
    # correction is still CRITICAL.
    if signals.is_public_claim:
        if signals.claim_direction == "asserting" or not signals.reversible:
            bump("CRITICAL", "asserts a new public claim, or the publication cannot be retracted")
        else:
            bump("HIGH", "corrective public claim that can itself be retracted")
    # Financial/legal impact is graded by whether the task EXECUTES the
    # commitment or merely touches a money-adjacent path. Editing a payment
    # handler is not the same as moving money; writing the ledger, or doing
    # either irreversibly, still is.
    if signals.financial_or_legal_impact:
        if (
            signals.financial_effect == "executes"
            or not signals.reversible
            or signals.writes_canonical_state
        ):
            bump("CRITICAL", "commits funds or legal obligation, is irreversible, or writes the canonical ledger")
        else:
            bump("HIGH", "touches a financial or legal code path without committing to it, reversibly")
    if signals.schema_or_migration and signals.writes_canonical_state:
        bump("CRITICAL", "schema change that migrates canonical state")
    if signals.production_or_credential_access and not signals.reversible:
        bump("CRITICAL", "irreversible action touching production or credentials")
    if not signals.reversible and signals.blast_radius in ("org", "public"):
        bump("CRITICAL", "irreversible action with org/public blast radius")
    if signals.privacy_class == "restricted" and not signals.reversible:
        bump("CRITICAL", "irreversible action on restricted-class data")

    # --- HIGH triggers -------------------------------------------------------
    if signals.writes_canonical_state:
        bump("HIGH", "writes to canonical (shared source-of-truth) state")
    # Schema work is graded by ENVIRONMENT. A staging column drop and a
    # production migration are not the same risk, but the ungraded rule
    # scored them identically. Non-production still floors MEDIUM (it affects
    # teammates), and never LOW; irreversible non-production work stays HIGH.
    # Production is unchanged, and the canonical-state CRITICAL trigger above
    # is independent of this block.
    if signals.schema_or_migration:
        if signals.environment == "production":
            bump("HIGH", "production schema or migration impact")
        elif not signals.reversible:
            bump("HIGH", f"irreversible schema change in {signals.environment}")
        else:
            bump("MEDIUM", f"reversible schema change confined to {signals.environment}")
    if signals.production_or_credential_access:
        bump("HIGH", "touches production or credential access")
    if signals.blast_radius in ("org", "public"):
        bump("HIGH", f"blast radius is {signals.blast_radius}")
    if signals.privacy_class in ("confidential", "restricted"):
        if signals.blast_radius == "local":
            bump("MEDIUM", f"{signals.privacy_class} data, but blast radius stays local")
        else:
            bump("HIGH", f"{signals.privacy_class} data leaving local blast radius")

    # --- MEDIUM triggers -------------------------------------------------------
    if not signals.reversible:
        bump("MEDIUM", "action is not reversible")
    # Team blast radius is graded by what the change actually does to the
    # team. A production-facing, irreversible, or breaking change still floors
    # MEDIUM. A reversible, purely additive change in a non-production
    # environment does not — that combination is the ordinary day-to-day work
    # the unconditional floor was over-routing. "Breaking" includes removing
    # or weakening an existing test or check, not just an API contract.
    if signals.blast_radius == "team":
        if (
            signals.environment == "production"
            or not signals.reversible
            or signals.change_shape == "breaking"
        ):
            bump("MEDIUM", "team-scoped change that is production-facing, irreversible, or breaking")

    flagged = signals.ambiguous and level in ("HIGH", "CRITICAL")
    rationale = "; ".join(reasons) if reasons else "no elevated-risk signals present; baseline LOW"
    return Classification(
        criticality=level,
        rationale=rationale,
        flagged_for_review=flagged,
        reasons=tuple(reasons),
    )
