from analyzer import AnalysisResult
from formatter import (
    format_analysis_message,
    format_parse_failure,
    split_for_telegram,
    tag_for_url,
)


def test_format_analysis_escapes_html_and_wraps_draft_in_pre_block():
    result = AnalysisResult(
        claim="<script>alert(1)</script>",
        verdict="Needs context.",
        form_misleading="yes",
        form_category="Factual error",
        form_harmful="no",
        draft_note="Note with <angle> & ampersand: https://example.com",
        sources=[{"url": "https://example.com/a.b", "description": "Source v1.0"}],
        raw_text="",
    )
    formatted = format_analysis_message(result, request_mode="analysis")

    # Claim is HTML-escaped
    assert "&lt;script&gt;" in formatted
    assert "<script>" not in formatted.replace("<script>alert(1)</script>", "")
    # Draft note is wrapped in <pre>
    assert "<pre>Note with &lt;angle&gt; &amp; ampersand: https://example.com</pre>" in formatted
    # URLs survive
    assert "https://example.com/a.b" in formatted


def test_format_analysis_outputs_sections_and_source_tags():
    result = AnalysisResult(
        claim="Claim text",
        verdict="Misleading",
        form_misleading="yes",
        form_category="Factual error",
        form_harmful="no",
        draft_note="Neutral note: https://example.com",
        sources=[
            {"url": "https://www.irs.gov/page", "description": "IRS data"},
            {"url": "https://www.nytimes.com/article", "description": "NYT report"},
        ],
        raw_text="",
    )

    formatted = format_analysis_message(result, request_mode="analysis")

    assert "Quick take" in formatted
    assert "Suggested Community Note" in formatted
    assert "Recommended form selections" in formatted
    assert "[gov] IRS data" in formatted
    assert "[media] NYT report" in formatted


def test_format_parse_failure_escapes_raw_text():
    formatted = format_parse_failure("raw <output> & more")

    assert "I couldn't finish the analysis" in formatted
    assert "&lt;output&gt;" in formatted
    assert "&amp;" in formatted


def test_format_analysis_revision_summary_label():
    result = AnalysisResult(
        claim="Original claim",
        verdict="Needs context",
        form_misleading="yes",
        form_category="Missing important context",
        form_harmful="no",
        draft_note="Revised note text",
        sources=[{"url": "https://example.com/context", "description": "Context"}],
        raw_text="",
    )

    formatted = format_analysis_message(result, request_mode="revision")
    assert "Updated draft ready" in formatted


def test_tag_for_url_categorizes_known_hosts():
    assert tag_for_url("https://www.irs.gov/x") == "gov"
    assert tag_for_url("https://pacer.uscourts.gov/x") == "court"
    assert tag_for_url("https://www.sec.gov/edgar") == "sec"
    assert tag_for_url("https://www.fec.gov/data") == "fec"
    assert tag_for_url("https://arxiv.org/abs/1234") == "research"
    assert tag_for_url("https://www.nytimes.com/x") == "media"
    assert tag_for_url("https://example.com/x") == "other"


def test_split_for_telegram_returns_single_chunk_when_short():
    text = "small message"
    assert split_for_telegram(text) == [text]


def test_split_for_telegram_breaks_on_blank_lines():
    para = "x" * 1000
    text = "\n\n".join([para] * 5)
    chunks = split_for_telegram(text, limit=2500)
    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk) <= 2500


def test_split_for_telegram_keeps_pre_block_intact():
    pre = "<pre>" + ("a" * 3000) + "</pre>"
    text = "intro\n\n" + pre + "\n\noutro"
    chunks = split_for_telegram(text, limit=1500)
    # The <pre> block must appear together (not split across chunks).
    found = False
    for chunk in chunks:
        if pre in chunk:
            found = True
            break
    assert found, "pre block was split across chunks"
