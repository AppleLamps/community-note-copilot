from analyzer import AnalysisResult
from formatter import format_analysis_message, format_parse_failure


def test_format_analysis_outputs_plain_text_sections_and_urls():
    result = AnalysisResult(
        claim="Claim with _chars_",
        verdict="Misleading",
        form_misleading="yes",
        form_category="Factual error",
        form_harmful="no",
        draft_note="Neutral note: https://example.com",
        sources=[{"url": "https://example.com", "description": "Primary source"}],
        raw_text="",
    )

    formatted = format_analysis_message(result, request_mode="analysis")

    assert "Quick take" in formatted
    assert "Suggested Community Note" in formatted
    assert "Recommended form selections" in formatted
    assert "Neutral note: https://example.com" in formatted
    assert "https://example.com" in formatted
    assert "Next prompts" in formatted
    assert "make it shorter" in formatted
    assert "Claim with _chars_" in formatted


def test_format_parse_failure_preserves_raw_text():
    formatted = format_parse_failure("raw output")

    assert "I couldn't finish the analysis" in formatted
    assert "Try sending the tweet URL again" in formatted
    assert "raw output" in formatted


def test_format_analysis_for_revision_suggests_revision_followups():
    result = AnalysisResult(
        claim="Original claim",
        verdict="Needs context",
        form_misleading="yes",
        form_category="Missing important context",
        form_harmful="no",
        draft_note="Revised note text",
        sources=[{"url": "https://example.com/context", "description": "Context source"}],
        raw_text="",
    )

    formatted = format_analysis_message(result, request_mode="revision")

    assert "Updated draft ready" in formatted
    assert "make it even shorter" in formatted
