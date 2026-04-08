from analyzer import AnalysisResult
from formatter import format_analysis_message, format_parse_failure


def test_format_analysis_escapes_markdown_and_lists_sources():
    result = AnalysisResult(
        claim="Claim with _chars_",
        verdict="Misleading",
        form_misleading="yes",
        form_category="Factual error",
        form_harmful="no",
        draft_note="Neutral note https://example.com",
        sources=[{"url": "https://example.com", "description": "Primary source"}],
        raw_text="",
    )

    formatted = format_analysis_message(result)

    assert "\\_" in formatted
    assert "*CN Form Selections*" in formatted
    assert "https://example.com" in formatted


def test_format_parse_failure_preserves_raw_text():
    formatted = format_parse_failure("raw output")

    assert "Structured parsing failed" in formatted
    assert "raw output" in formatted
