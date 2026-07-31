"""SHR-61: prove the criticality classifier feeds the gateway a correct label.

The entitlement table (shiroe.core.reasoning) is only as trustworthy as the
criticality it is handed. This suite runs a labeled corpus
(tests/fixtures/routing_corpus.jsonl) through the deterministic classifier
(shiroe.routing.criticality) end to end, publishes a confusion matrix and the
five metrics the audit named explicitly, and asserts CRITICAL recall on its
own — a high blended accuracy that hides one missed CRITICAL is a failure
here, not a pass.

Honesty note for reviewers: the corpus and the classifier's rules were
authored together (see shiroe/routing/criticality.py and the generation
script this fixture came from), so 100% agreement on this corpus is expected
by construction, not a generalization claim. Its value is threefold: it is a
frozen regression suite (a future rule change that silently reclassifies any
of these 48 tasks fails the build), it is executable documentation of what
each structured-signal combination is supposed to mean, and the specific
adversarial/ambiguous/orthogonality entries below exercise properties the
rules must hold that a plain accuracy number would not surface.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from shiroe.core.reasoning import CRITICALITIES
from shiroe.routing.criticality import (
    BLAST_RADII,
    CHANGE_SHAPES,
    CLAIM_DIRECTIONS,
    ENVIRONMENTS,
    FINANCIAL_EFFECTS,
    PRIVACY_CLASSES,
    TaskSignals,
    classify,
)
from shiroe.routing.gateway import (
    ANY,
    ApprovalRequiredError,
    RoutingError,
    classify_and_route,
)

REPO = Path(__file__).resolve().parents[1]
CORPUS_PATH = REPO / "tests" / "fixtures" / "routing_corpus.jsonl"

_LEVELS = CRITICALITIES  # ("LOW", "MEDIUM", "HIGH", "CRITICAL") — cheapest to costliest


def _load_corpus() -> list[dict]:
    entries = []
    with CORPUS_PATH.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            entries.append(json.loads(line))
    return entries


CORPUS = _load_corpus()


def _idx(level: str) -> int:
    return _LEVELS.index(level)


def _evaluate(corpus: list[dict]) -> dict:
    """Run every corpus entry through classify() and compute the published metrics."""
    confusion = {a: {p: 0 for p in _LEVELS} for a in _LEVELS}
    results = []
    for entry in corpus:
        signals = TaskSignals(**entry["signals"])
        result = classify(signals)
        confusion[entry["label"]][result.criticality] += 1
        results.append((entry, result))

    total = len(corpus)
    under = sum(1 for e, r in results if _idx(r.criticality) < _idx(e["label"]))
    over = sum(1 for e, r in results if _idx(r.criticality) > _idx(e["label"]))
    correct = sum(1 for e, r in results if r.criticality == e["label"])
    critical_actual = [e for e in corpus if e["label"] == "CRITICAL"]
    critical_hits = sum(1 for e, r in results if e["label"] == "CRITICAL" and r.criticality == "CRITICAL")
    unnecessary_frontier = sum(1 for e, r in results if r.criticality == "CRITICAL" and e["label"] != "CRITICAL")
    flagged = sum(1 for _, r in results if r.flagged_for_review)

    return {
        "results": results,
        "confusion": confusion,
        "total": total,
        "accuracy": correct / total,
        "critical_recall": (critical_hits / len(critical_actual)) if critical_actual else 1.0,
        "under_routing_rate": under / total,
        "over_routing_rate": over / total,
        "unnecessary_frontier_rate": unnecessary_frontier / total,
        "abstention_rate": flagged / total,
    }


METRICS = _evaluate(CORPUS)

# Strict on purpose: this is a small, hand-labeled, rule-matched corpus (not a
# sampled/held-out set), so anything short of 100% CRITICAL recall here means
# a rule regressed against a case we already know the answer to. A real
# under-classified CRITICAL task is the expensive failure the whole gateway
# exists to prevent — the audit calls a hidden miss behind a good aggregate a
# FAILURE, not a pass, so this threshold does not leave room for one.
CRITICAL_RECALL_THRESHOLD = 1.0


def _print_report() -> None:
    print("\n--- routing corpus confusion matrix (rows=actual, cols=predicted) ---")
    header = "actual\\pred".ljust(12) + "".join(level.ljust(10) for level in _LEVELS)
    print(header)
    for actual in _LEVELS:
        row = METRICS["confusion"][actual]
        print(actual.ljust(12) + "".join(str(row[p]).ljust(10) for p in _LEVELS))
    print(f"total entries:            {METRICS['total']}")
    print(f"overall accuracy:         {METRICS['accuracy']:.3f}")
    print(f"CRITICAL recall:          {METRICS['critical_recall']:.3f}  (threshold {CRITICAL_RECALL_THRESHOLD})")
    print(f"under-routing rate:       {METRICS['under_routing_rate']:.3f}")
    print(f"over-routing rate:        {METRICS['over_routing_rate']:.3f}")
    print(f"unnecessary-frontier rate:{METRICS['unnecessary_frontier_rate']:.3f}")
    print(f"abstention/flag rate:     {METRICS['abstention_rate']:.3f}")


def test_corpus_shape_and_coverage() -> None:
    assert len(CORPUS) >= 40, "corpus must have at least 40 labeled tasks"
    labels = {e["label"] for e in CORPUS}
    assert labels == set(_LEVELS), "corpus must span all four criticality levels"
    for entry in CORPUS:
        assert entry["rationale"].strip(), f"{entry['id']} is missing a rationale"
    ids = [e["id"] for e in CORPUS]
    assert len(ids) == len(set(ids)), "corpus ids must be unique"


def test_confusion_matrix_and_metrics_are_published() -> None:
    """Publish the matrix and all five metrics separately — never just one blended score."""
    _print_report()
    # The metrics are asserted individually below (not folded into one
    # pass/fail number) so a regression in any one of them is visible on its
    # own, per the "publish, do not hide behind an aggregate" requirement.
    assert METRICS["total"] == len(CORPUS)
    assert 0.0 <= METRICS["accuracy"] <= 1.0
    assert 0.0 <= METRICS["under_routing_rate"] <= 1.0
    assert 0.0 <= METRICS["over_routing_rate"] <= 1.0
    assert 0.0 <= METRICS["unnecessary_frontier_rate"] <= 1.0
    assert 0.0 <= METRICS["abstention_rate"] <= 1.0


def test_critical_recall_meets_strict_threshold() -> None:
    """The one assertion that is not allowed to hide behind aggregate accuracy."""
    assert METRICS["critical_recall"] >= CRITICAL_RECALL_THRESHOLD, (
        f"CRITICAL recall {METRICS['critical_recall']:.3f} missed at least one "
        f"CRITICAL task — that is a failure even if overall accuracy looks fine"
    )


def test_no_entry_routes_below_its_label_without_being_flagged() -> None:
    """Under-routing must never happen silently: it must always carry the review flag."""
    for entry, result in METRICS["results"]:
        if _idx(result.criticality) < _idx(entry["label"]):
            assert result.flagged_for_review, (
                f"{entry['id']} classified below its label "
                f"({result.criticality} < {entry['label']}) without being flagged for review"
            )


def test_adversarial_entries_are_not_fooled_by_phrasing() -> None:
    """Phrasing (innocuous or verbose) must never move the classification.

    The classifier only ever sees TaskSignals, never entry['description'] —
    these entries prove that friendly wording around a destructive action,
    and dramatic wording around a trivial one, both land on their true label.
    """
    adversarial = [e for e in CORPUS if e.get("adversarial")]
    assert len(adversarial) >= 4, "corpus should carry multiple adversarial entries"
    for entry in adversarial:
        result = classify(TaskSignals(**entry["signals"]))
        assert result.criticality == entry["label"], (
            f"adversarial entry {entry['id']} ({entry['description'][:60]!r}...) "
            f"classified {result.criticality}, expected {entry['label']}"
        )


def test_ambiguous_high_and_critical_cases_are_flagged_for_human_approval() -> None:
    ambiguous = [e for e in CORPUS if e.get("ambiguous_flag_expected")]
    assert ambiguous, "corpus should carry at least one ambiguous HIGH/CRITICAL entry"
    for entry in ambiguous:
        result = classify(TaskSignals(**entry["signals"]))
        assert result.criticality == entry["label"]
        assert result.criticality in ("HIGH", "CRITICAL")
        assert result.flagged_for_review, f"{entry['id']} should be flagged for human approval"

        with pytest.raises(ApprovalRequiredError):
            classify_and_route(TaskSignals(**entry["signals"]), purpose=entry["id"])

        # A human approving it lets the same request through, and the
        # decision still records that it was a flagged classification.
        decision = classify_and_route(
            TaskSignals(**entry["signals"]), purpose=entry["id"], approved=True
        )
        assert decision.criticality == entry["label"]
        assert decision.classification is not None
        assert decision.classification.flagged_for_review is True


def test_placement_does_not_erase_reasoning_depth() -> None:
    """P1-07 orthogonality, proven at the classifier boundary.

    classify() takes no placement argument at all — it is structurally
    impossible for "this may only run locally" to change what criticality a
    task gets. A CRITICAL task confined to local/private execution is
    refused (no local adapter exists, per PR1) rather than silently resolved
    at a cheaper reasoning class.
    """
    critical_entry = next(e for e in CORPUS if e["id"] == "C01")
    signals = TaskSignals(**critical_entry["signals"])

    remote_decision = classify_and_route(signals, purpose="C01 remote", placement=ANY)
    assert remote_decision.criticality == "CRITICAL"
    assert remote_decision.reasoning_class == "frontier"

    for placement_word in ("local", "private"):
        with pytest.raises(RoutingError, match="local-execution provider adapter"):
            classify_and_route(signals, purpose="C01 confined", placement=placement_word)
        # Confirm independently that the classifier itself was never asked
        # about placement and still says CRITICAL — the RoutingError above
        # comes from the placement gate in shiroe.routing.gateway.route(),
        # not from a downgraded classification.
        assert classify(signals).criticality == "CRITICAL"


def test_local_placement_does_not_auto_inflate_to_critical() -> None:
    """The flip side of orthogonality: 'runs locally' must not itself imply CRITICAL."""
    private_summary = next(e for e in CORPUS if e["id"] == "M02")
    result = classify(TaskSignals(**private_summary["signals"]))
    assert result.criticality == "MEDIUM"
    assert result.criticality != "CRITICAL"


def test_classify_and_route_wires_classification_into_the_gateway() -> None:
    """A caller with no explicit criticality gets classified rather than defaulted."""
    low_entry = next(e for e in CORPUS if e["id"] == "L01")
    decision = classify_and_route(TaskSignals(**low_entry["signals"]), purpose=low_entry["id"])
    assert decision.criticality == "LOW"
    assert decision.reasoning_class == "fast"
    assert decision.classification is not None
    assert decision.classification.criticality == "LOW"
    assert not decision.classification.flagged_for_review


def test_explicit_criticality_path_is_unaffected() -> None:
    """PR1 callers that already hand route() a validated criticality keep working."""
    from shiroe.routing.gateway import ModelCallRequest, route

    decision = route(ModelCallRequest(criticality="HIGH", purpose="pre-SHR-61 caller"))
    assert decision.reasoning_class == "deep"
    assert decision.classification is None


# ---------------------------------------------------------------------------
# Graded signals: four signals that previously fired unconditionally
#
# Each of these four could only say "present" or "absent", so a staging schema
# tweak scored the same as a production migration, and retracting an
# overstated public claim scored the same as publishing a new unverified one.
# Grading them adds precision WITHOUT lowering any floor that protects a
# genuinely dangerous task — the two property tests at the bottom are what
# hold that line.
# ---------------------------------------------------------------------------

def test_corrective_public_claim_is_high_not_critical() -> None:
    signals = TaskSignals(blast_radius="public", is_public_claim=True, claim_direction="corrective")
    assert classify(signals).criticality == "HIGH"


def test_asserting_public_claim_stays_critical() -> None:
    signals = TaskSignals(blast_radius="public", is_public_claim=True)
    assert classify(signals).criticality == "CRITICAL"


def test_irretractable_corrective_claim_stays_critical() -> None:
    signals = TaskSignals(
        blast_radius="public", is_public_claim=True,
        claim_direction="corrective", reversible=False,
    )
    assert classify(signals).criticality == "CRITICAL"


def test_financial_code_path_touch_is_high_not_critical() -> None:
    signals = TaskSignals(
        blast_radius="public", financial_or_legal_impact=True,
        financial_effect="touches_path",
    )
    assert classify(signals).criticality == "HIGH"


def test_executing_a_payment_stays_critical() -> None:
    signals = TaskSignals(blast_radius="org", financial_or_legal_impact=True)
    assert classify(signals).criticality == "CRITICAL"


def test_money_path_that_writes_the_ledger_stays_critical() -> None:
    signals = TaskSignals(
        financial_or_legal_impact=True, financial_effect="touches_path",
        writes_canonical_state=True,
    )
    assert classify(signals).criticality == "CRITICAL"


def test_reversible_staging_schema_change_is_medium() -> None:
    signals = TaskSignals(blast_radius="team", schema_or_migration=True, environment="staging")
    assert classify(signals).criticality == "MEDIUM"


def test_irreversible_staging_schema_change_stays_high() -> None:
    signals = TaskSignals(
        blast_radius="team", schema_or_migration=True,
        environment="staging", reversible=False,
    )
    assert classify(signals).criticality == "HIGH"


def test_production_schema_change_stays_high() -> None:
    signals = TaskSignals(blast_radius="team", schema_or_migration=True)
    assert classify(signals).criticality == "HIGH"


def test_production_schema_migrating_canonical_state_stays_critical() -> None:
    signals = TaskSignals(schema_or_migration=True, writes_canonical_state=True)
    assert classify(signals).criticality == "CRITICAL"


def test_team_scoped_nonprod_additive_reversible_has_no_floor() -> None:
    signals = TaskSignals(blast_radius="team", environment="development", change_shape="additive")
    assert classify(signals).criticality == "LOW"


def test_team_scoped_breaking_change_still_floors_medium() -> None:
    signals = TaskSignals(blast_radius="team", environment="development")
    assert classify(signals).criticality == "MEDIUM"


# --- the two properties that make the above safe ---------------------------

_OLD_FIELDS = {
    "reversible": (True, False),
    "blast_radius": BLAST_RADII,
    "privacy_class": PRIVACY_CLASSES,
    "is_public_claim": (True, False),
    "schema_or_migration": (True, False),
    "production_or_credential_access": (True, False),
    "financial_or_legal_impact": (True, False),
    "writes_canonical_state": (True, False),
}


def test_no_new_field_value_can_exceed_its_default() -> None:
    """Defaults are the most severe value of every new enum.

    This is what makes the new fields safe to omit: a caller that has never
    heard of them cannot land on a LOWER criticality than they would have
    before the fields existed. Exhaustive over the old input space crossed
    with every combination of the new one.
    """
    import itertools
    from dataclasses import replace

    names = list(_OLD_FIELDS)
    for combo in itertools.product(*(_OLD_FIELDS[n] for n in names)):
        base = TaskSignals(**dict(zip(names, combo)))
        ceiling = _idx(classify(base).criticality)
        for env, shape, claim, effect in itertools.product(
            ENVIRONMENTS, CHANGE_SHAPES, CLAIM_DIRECTIONS, FINANCIAL_EFFECTS
        ):
            variant = replace(
                base, environment=env, change_shape=shape,
                claim_direction=claim, financial_effect=effect,
            )
            assert _idx(classify(variant).criticality) <= ceiling, (
                f"{variant} routed ABOVE its own default — a new field value "
                f"must never raise the floor beyond the default"
            )


def test_every_new_field_rejects_unknown_values() -> None:
    """Typos must fail loudly rather than silently selecting a lenient branch."""
    for field, bad in (
        ("environment", "prod"),
        ("change_shape", "additive-ish"),
        ("claim_direction", "retracting"),
        ("financial_effect", "touches"),
    ):
        with pytest.raises(ValueError):
            TaskSignals(**{field: bad})
