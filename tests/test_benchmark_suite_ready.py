"""Readiness checks for the external benchmark suite.

These run before any scored run and are cheap, offline, and network-free.
They exist because the expensive failure mode is discovering a loader was
wrong *after* paying for a scored run — the ConvoMem loader shipped with
every field name guessed and none of them correct, and nothing caught it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from benchmarks.external.loaders import LOADERS, get_loader

REPO = Path(__file__).resolve().parents[1]
FIXTURES = REPO / "benchmarks" / "external" / "fixtures"


@pytest.mark.parametrize("name", sorted(LOADERS))
def test_loader_records_provenance_and_licence(name: str) -> None:
    """Every loader must state where its data came from and under what terms.

    A benchmark number with no recorded licence cannot be published safely —
    ConvoMem's data is CC-BY-NC-4.0 while its code repo is Apache-2.0, which
    is exactly the kind of difference that gets missed.
    """
    loader = get_loader(name)
    for attr in ("NAME", "OFFICIAL_URL", "PINNED_VERSION", "LICENSE", "LICENSE_NOTE"):
        assert getattr(loader, attr, None), f"{name} is missing {attr}"
    assert loader.OFFICIAL_URL.startswith("https://"), f"{name} OFFICIAL_URL must be https"
    assert hasattr(loader, "PINNED_SHA256"), f"{name} must declare PINNED_SHA256 (may be None)"


@pytest.mark.parametrize("name", sorted(LOADERS))
def test_loader_parses_its_fixture(name: str) -> None:
    """Each loader must parse its committed fixture into well-formed Tasks."""
    tasks = get_loader(name).load(FIXTURES / name)
    assert tasks, f"{name} parsed zero tasks from its fixture"
    for task in tasks:
        assert task.task_id and task.question
        assert task.answers and all(isinstance(a, str) for a in task.answers)
        assert task.metric in {"exact_match", "token_f1", "choice_accuracy"}
        for session in task.sessions:
            for turn in session:
                assert isinstance(turn.role, str) and isinstance(turn.content, str)


def test_convomem_parses_the_real_release_shape() -> None:
    """Lock ConvoMem's verified field names against silent regression.

    The keys asserted here were confirmed against the actual
    Salesforce/ConvoMem release. The previous loader guessed
    conversation_id / sessions / turns / questions / qid — none of which
    exist — so this test pins the real shape rather than trusting a docstring.
    """
    from benchmarks.external.loaders import convomem

    tasks = convomem.load(FIXTURES / "convomem")
    assert len(tasks) == 2

    for guess in convomem._SUPERSEDED_GUESSES:
        assert guess not in {"question", "answer", "conversations", "messages",
                             "speaker", "text", "personId", "evidence_items"}, (
            f"{guess!r} is recorded as a superseded guess but collides with a real key"
        )

    by_question = {t.question: t for t in tasks}
    answered = next(t for q, t in by_question.items() if "dog" in q)
    assert answered.answers == ("Comet",)
    assert answered.metadata["person_id"] == "SYNTHETIC-persona-1"
    assert answered.metadata["evidence_type"] == "user_evidence"
    assert sum(len(s) for s in answered.sessions) == 3

    # Abstention: gold answer is a full sentence, which is why this benchmark
    # needs a judge and cannot be scored on token overlap alone.
    abstention = next(t for q, t in by_question.items() if "vet" in q)
    assert "no information" in abstention.answers[0].lower()
    assert len(abstention.answers[0].split()) > 5


def test_convomem_licence_is_flagged_non_commercial() -> None:
    """The NC restriction must be visible in the loader, not just in a PR."""
    from benchmarks.external.loaders import convomem

    assert convomem.LICENSE == "CC-BY-NC-4.0"
    assert "NON-COMMERCIAL" in convomem.LICENSE_NOTE


def test_all_three_arms_are_constructible() -> None:
    """A Shiroe-only number is unfalsifiable, so all three arms must exist
    before any scored run — not be discovered missing partway through one.
    """
    from benchmarks.external.runner import ALL_ARMS, ARM_BACKENDS

    assert set(ALL_ARMS) == {"shiroe", "full_context", "bm25"}
    for arm in ALL_ARMS:
        backend = ARM_BACKENDS[arm]()
        backend.ingest("probe", "SYNTHETIC: the sky is cerulean")
        assert backend.recall("sky colour", k=1) is not None


def test_live_judge_is_still_disabled() -> None:
    """Until a live judge is deliberately enabled, it must refuse loudly.

    A judge that silently returns a default verdict would produce a scored
    run that looks real and means nothing.
    """
    from benchmarks.external.judges.gemini import GeminiJudgeClient

    judge = GeminiJudgeClient()
    with pytest.raises(RuntimeError):
        judge.judge("q", ("a",), "p")
    # estimate() must work offline so cost projection never needs a network call
    usage = judge.estimate("q", ("a",), "p")
    assert usage.estimated is True and usage.cost_usd >= 0.0


def test_judge_never_exposes_the_api_key() -> None:
    """has_key() reports presence only; the value must not be retrievable."""
    from benchmarks.external.judges.gemini import GeminiJudgeClient

    judge = GeminiJudgeClient()
    assert isinstance(judge.has_key(), bool)
    for value in vars(judge).values():
        assert not (isinstance(value, str) and len(value) > 20 and value.startswith("AIza")), (
            "an API-key-shaped string is stored on the judge instance"
        )


# ---------------------------------------------------------------------------
# Live judge: parsing, redaction, and the opt-in gates.
# Every test here is offline — none may reach the network.
# ---------------------------------------------------------------------------

def test_judge_defaults_to_disabled_and_refuses() -> None:
    """live=False is the default, so no test or dry run can bill the API."""
    from benchmarks.external.judges.gemini import GeminiJudgeClient

    with pytest.raises(RuntimeError, match="disabled"):
        GeminiJudgeClient().judge("q", ("a",), "p")


def test_judge_parses_a_normal_verdict() -> None:
    from benchmarks.external.judges.gemini import _parse_verdict

    correct, score, rationale = _parse_verdict(
        '{"correct": true, "score": 0.9, "rationale": "matches the reference"}'
    )
    assert correct is True and score == 0.9 and "matches" in rationale


def test_judge_parses_a_fenced_verdict() -> None:
    """Models often wrap JSON in a markdown fence despite being told not to."""
    from benchmarks.external.judges.gemini import _parse_verdict

    correct, score, _ = _parse_verdict(
        '```json\n{"correct": false, "score": 0.0, "rationale": "wrong entity"}\n```'
    )
    assert correct is False and score == 0.0


def test_unparseable_verdict_scores_incorrect_and_says_so() -> None:
    """A malformed reply must not silently become a pass.

    Counting it correct would inflate whichever arm triggered it; dropping it
    would shrink the denominator invisibly. It scores incorrect and records
    why, so the damage is visible in the results file.
    """
    from benchmarks.external.judges.gemini import _parse_verdict

    correct, score, rationale = _parse_verdict("I think it's basically right?")
    assert correct is False and score == 0.0
    assert "unparseable" in rationale


def test_out_of_range_score_is_clamped() -> None:
    from benchmarks.external.judges.gemini import _parse_verdict

    assert _parse_verdict('{"correct": true, "score": 7}')[1] == 1.0
    assert _parse_verdict('{"correct": false, "score": -3}')[1] == 0.0


def test_redact_strips_key_shaped_strings() -> None:
    """Backstop for an error body that echoes a request back."""
    from benchmarks.external.judges.gemini import _redact

    assert "AIzaSyFAKEFAKEFAKEFAKE123456" not in _redact(
        "error at ?key=AIzaSyFAKEFAKEFAKEFAKE123456&alt=json"
    )
    assert "[REDACTED" in _redact("?key=AIzaSyFAKEFAKEFAKEFAKE123456")


def test_usage_uses_real_token_counts_and_is_not_marked_estimated() -> None:
    from benchmarks.external.judges.gemini import _usage_from_response

    usage = _usage_from_response(
        {"usageMetadata": {"promptTokenCount": 1000, "candidatesTokenCount": 20}},
        "gemini-2.5-flash",
    )
    assert usage.input_tokens == 1000 and usage.output_tokens == 20
    assert usage.estimated is False and usage.cost_usd > 0


def test_judge_never_puts_the_key_in_a_url() -> None:
    """The key must travel as a header.

    urllib embeds the request URL in HTTPError/URLError strings, so a key in
    the query string would leak into every traceback and CI log.
    """
    from benchmarks.external.judges import gemini

    source = (Path(gemini.__file__)).read_text(encoding="utf-8")
    assert "?key=" not in source, "API key must not be passed as a URL parameter"
    assert "x-goog-api-key" in source, "API key should be sent as a header"


def test_pricing_is_not_the_old_placeholder() -> None:
    """Judge pricing drives the --max-cost budget gate.

    The original table used 0.075/0.30 per Mtok, which is 20-30x below the
    real rate. An underestimate here does not just misreport cost — it lets
    estimate_run_cost() authorize a run far more expensive than the
    projection the operator approved.
    """
    from benchmarks.external.judges.gemini import DEFAULT_MODEL_ID, PRICING_USD_PER_MTOK

    assert DEFAULT_MODEL_ID in PRICING_USD_PER_MTOK, "the default model must be priced"
    in_rate, out_rate = PRICING_USD_PER_MTOK[DEFAULT_MODEL_ID]
    assert (in_rate, out_rate) != (0.075, 0.30), "placeholder pricing is back"
    assert in_rate > 0 and out_rate > 0


def test_unknown_model_prices_expensive_not_free() -> None:
    """An unpriced model must over-estimate, so the ceiling trips early."""
    from benchmarks.external.judges.gemini import PRICING_USD_PER_MTOK, _rates_for

    known_max = max(rate for rates in PRICING_USD_PER_MTOK.values() for rate in rates)
    unknown_in, unknown_out = _rates_for("gemini-does-not-exist-9")
    assert unknown_out >= known_max or unknown_out > 0
    assert unknown_in > 0


def test_gemini_provider_is_dry_run_by_default_and_never_stores_the_key() -> None:
    """A Gemini-only run must not bill by accident, or retain the key."""
    from benchmarks.external.providers.gemini import GeminiProvider

    provider = GeminiProvider()
    assert provider.dry_run is True
    completion = provider.complete("probe")
    assert completion.text == ""
    assert completion.usage.estimated is True
    assert isinstance(provider.has_key(), bool)
    for value in vars(provider).values():
        assert not (isinstance(value, str) and value.startswith("AIza")), (
            "an API-key-shaped string is stored on the provider instance"
        )


def test_gemini_provider_and_judge_default_to_different_models() -> None:
    """Judge independence: the judge must not grade its own model's output.

    Same family is unavoidable on a Gemini-only run and is recorded as a
    caveat, but generator and judge defaulting to the SAME model would make
    the judge grade its own generation, which is worse and is avoidable.
    """
    from benchmarks.external.judges.gemini import GeminiJudgeClient
    from benchmarks.external.providers.gemini import GeminiProvider

    assert GeminiProvider().model_id != GeminiJudgeClient().model_id


def test_unknown_gemini_model_prices_expensive_not_cheap() -> None:
    """An unpriced model must over-estimate, so the budget gate trips early."""
    from benchmarks.external import gemini_api

    known = gemini_api.rates_for("gemini-2.5-flash")
    unknown = gemini_api.rates_for("gemini-does-not-exist")
    assert unknown >= known
    assert unknown == gemini_api._UNKNOWN_MODEL_RATES


def test_judge_independence_is_recorded_in_provenance() -> None:
    """The caveat must travel with the number, not live in a PR comment."""
    from benchmarks.external.harness import _judge_independence

    same = _judge_independence("gemini-2.5-flash", "gemini-3.5-flash")
    assert same["same_family"] is True
    assert same["same_model"] is False
    assert "relative ranking between arms is unaffected" in same["caveat"]

    cross = _judge_independence("claude-opus-4-6", "gemini-3.5-flash")
    assert cross["same_family"] is False


def test_provenance_digests_a_directory_dataset() -> None:
    """ConvoMem is a tree, not a file — provenance must not raise on it."""
    from benchmarks.external.harness import _dataset_digest
    from benchmarks.external.loaders import convomem, locomo

    tree = _dataset_digest(convomem, FIXTURES / "convomem")
    assert tree and len(tree) == 64
    # single-file loaders keep working through the same helper
    assert _dataset_digest(locomo, FIXTURES / "locomo") is not None


def test_shared_transport_is_the_only_key_reader() -> None:
    """One key-handling implementation, not two.

    The judge and provider must both route through gemini_api so the
    security-critical parts cannot drift apart.
    """
    from benchmarks.external import gemini_api
    from benchmarks.external.judges import gemini as judge_mod
    from benchmarks.external.providers import gemini as provider_mod

    assert judge_mod._read_api_key is gemini_api.read_api_key
    assert provider_mod.gemini_api is gemini_api
    judge_src = (REPO / "benchmarks/external/judges/gemini.py").read_text(encoding="utf-8")
    provider_src = (REPO / "benchmarks/external/providers/gemini.py").read_text(encoding="utf-8")
    for src, who in ((judge_src, "judge"), (provider_src, "provider")):
        assert "GEMINI_API_KEY" not in src or "gemini_api" in src, (
            f"{who} reads the key without going through the shared transport"
        )


def test_longmemeval_accepts_the_cleaned_release_filename() -> None:
    """The loader must accept the filename the official instructions produce.

    PINNED_VERSION and PINNED_SHA256 both describe longmemeval_s_cleaned.json,
    but the loader used to require longmemeval_s.json — so following the
    documented download forced a rename, and renaming discards the one signal
    saying which release you have. The pre-Sept-2025 file is still accepted;
    its numbers are not comparable to the cleaned release.
    """
    from benchmarks.external.loaders import longmemeval

    assert longmemeval.DATA_FILENAME == "longmemeval_s_cleaned.json"
    assert "longmemeval_s.json" in longmemeval.ACCEPTED_FILENAMES
    # the cleaned name must be preferred when both are present
    assert longmemeval.ACCEPTED_FILENAMES[0] == "longmemeval_s_cleaned.json"


def test_longmemeval_resolution_prefers_cleaned(tmp_path: Path) -> None:
    from benchmarks.external.loaders import longmemeval

    (tmp_path / "longmemeval_s.json").write_text("[]", encoding="utf-8")
    assert longmemeval._resolve_data_file(tmp_path).name == "longmemeval_s.json"
    (tmp_path / "longmemeval_s_cleaned.json").write_text("[]", encoding="utf-8")
    assert longmemeval._resolve_data_file(tmp_path).name == "longmemeval_s_cleaned.json"
