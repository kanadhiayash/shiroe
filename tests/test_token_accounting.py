"""SHR-62: provider-aware token accounting.

The old estimator counted whitespace-separated runs (``\\S+``), so any dense
or non-Latin-script text (CJK, Devanagari, Arabic, minified JSON/code,
base64) has few or no ASCII spaces and collapsed to ~2 estimated tokens —
silently undercounting and walking straight through every budget check.
These tests assert no content class can materially undercount, English
prose stays in a sane (not wildly inflated) band, and the layered estimator
reports which layer actually produced the number via ``method``.
"""

from __future__ import annotations

from shiroe.memory.cost_router import DEFAULT_POLICY, estimate_tokens, route_operation

# Same content classes as the SHR-62 baseline reproduction.
CONTENT_CLASSES = {
    "cjk": "你好" * 200,
    "devanagari": "नमस्तेदुनिया" * 100,
    "arabic": "مرحبابالعالم" * 100,
    "dense_json": '{"items":[' + ",".join(['{"id":1,"value":"abcdef"}'] * 50) + "]}",
    "base64_like": "QUJDREVGR0hJSktMTU5PUFFSU1RVVldYWVo9" * 20,
    "source": "functionx(){returnabcdef1234567890;}" * 50,
    "long_url": "https://example.com/" + "a" * 1000,
}

ENGLISH_PROSE = "word " * 100

# The old estimator returned 2 for every class above. A conservative floor
# of 200 catches any regression back toward that defect while leaving
# headroom for legitimately shorter payloads.
UNDERCOUNT_FLOOR = 200


def test_no_content_class_materially_undercounts() -> None:
    for name, text in CONTENT_CLASSES.items():
        estimate = estimate_tokens(text)
        assert estimate["estimated_tokens"] >= UNDERCOUNT_FLOOR, (
            f"{name}: estimated {estimate['estimated_tokens']} tokens for "
            f"{len(text)} chars — below the {UNDERCOUNT_FLOOR}-token floor, "
            "regression toward the whitespace-only undercount defect"
        )


def test_english_prose_stays_in_a_sane_band() -> None:
    estimate = estimate_tokens(ENGLISH_PROSE)
    word_count = len(ENGLISH_PROSE.split())
    # Must not regress to the old undercount (2 tokens for 100 words), and
    # must not swing to wild overcounting either — conservative, not absurd.
    assert word_count <= estimate["estimated_tokens"] <= word_count * 3


def test_method_reports_the_layer_actually_used() -> None:
    fallback = estimate_tokens("hello world")
    assert fallback["method"] == "conservative_max_signal"

    provider = estimate_tokens("hello world", actual_tokens=42)
    assert provider["method"] == "provider_actual"
    assert provider["estimated_tokens"] == 42

    empty = estimate_tokens("")
    assert empty["method"] == "empty"
    assert empty["estimated_tokens"] == 0


def test_dict_shape_is_backward_compatible() -> None:
    estimate = estimate_tokens("some text")
    assert set(estimate) == {"estimated_tokens", "estimated_chars", "method"}
    assert isinstance(estimate["estimated_tokens"], int)
    assert isinstance(estimate["estimated_chars"], int)
    assert isinstance(estimate["method"], str)


def test_dense_non_latin_text_now_exceeds_the_memory_write_budget() -> None:
    """Regression guard for the defect itself: previously this routed to
    a plain no-write decision because it looked like ~2 tokens; now it
    must be recognized as exceeding the memory-write budget.

    SHR-63 note: the original probe used the operation name "some-view",
    which is not a real operation route_operation() recognizes anywhere
    else in this codebase — it only reached the budget check because
    unrecognized operations used to fall through to the generic
    budget-or-no-write path (the exact defect SHR-63 closes: unknown
    operations now fail closed instead). Swapped to "memory-add", a real
    operation, so this test still exercises the token-estimate regression
    it was written for without depending on that now-fixed loophole.
    """
    budget = DEFAULT_POLICY["max_context_tokens_for_memory_write"]
    oversized_cjk = "你好世界" * 500  # ~2000 chars, well past the 1200 budget
    result = route_operation("memory-add", text=oversized_cjk)
    assert result["estimate"]["estimated_tokens"] > budget
    assert result["ladder_step"] == "flagship-review"


def test_existing_route_operation_decisions_still_hold() -> None:
    # Spot-check a few decisions the rest of the suite depends on, to make
    # sure raising the estimate didn't change non-budget-driven routing.
    assert route_operation("markdown-rewrite")["executor"] == "blocked"
    assert route_operation("memory-add", duplicate=True)["ladder_step"] == "link-existing"
    assert route_operation("patch", status_change=True)["ladder_step"] == "atom-patch"
    assert route_operation("memory-add", public_claim=True)["executor"] == "flagship"
    # SHR-63 note: empty-string was previously used here to assert a
    # "no-write" decision for "no operation, no text". That relied on the
    # same defect fixed above — an unrecognized operation (empty string is
    # not a real operation name) falling through to a generic no-write
    # default instead of failing closed. It now correctly fails closed.
    assert route_operation("")["executor"] == "blocked"
