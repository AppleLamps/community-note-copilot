import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from analyzer import (
    AnalysisResult,
    ANALYSIS_JSON_SCHEMA,
    XAIAnalyzer,
    build_revision_input,
    extract_output_text,
    load_settings,
    parse_analysis_response,
)
from config import Settings


def test_project_imports():
    import analyzer  # noqa: F401
    import formatter  # noqa: F401
    import storage  # noqa: F401


def test_load_settings_reads_required_env(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "telegram-token")
    monkeypatch.setenv("XAI_API_KEY", "xai-key")

    settings = load_settings()

    assert settings.telegram_bot_token == "telegram-token"
    assert settings.xai_api_key == "xai-key"
    assert settings.xai_model == "grok-4.20-0309-reasoning"
    assert settings.sqlite_path.endswith(".sqlite3")


def test_load_settings_requires_critical_env(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    monkeypatch.setitem(sys.modules, "dotenv", SimpleNamespace(load_dotenv=lambda: None))

    with pytest.raises(ValueError):
        load_settings()


def test_extract_output_text_prefers_output_text_property():
    class FakeResponse:
        output_text = '{"claim":"A"}'

    assert extract_output_text(FakeResponse()) == '{"claim":"A"}'


def test_extract_output_text_falls_back_to_output_blocks():
    class Content:
        type = "output_text"
        text = '{"claim":"B"}'

    class Message:
        type = "message"
        content = [Content()]

    class FakeResponse:
        output_text = ""
        output = [Message()]

    assert extract_output_text(FakeResponse()) == '{"claim":"B"}'


def test_parse_json_payload_and_collect_sources():
    response_text = json.dumps(
        {
            "claim": "A claim",
            "verdict": "Missing Context",
            "form_misleading": "yes",
            "form_category": "Missing important context",
            "form_harmful": "no",
            "draft_note": "Context here https://a.example/source",
            "sources": [{"url": "https://a.example/source", "description": "Primary source"}],
        }
    )

    parsed = parse_analysis_response(
        response_text,
        [{"url": "https://b.example/extra", "title": "Extra source"}],
    )

    assert isinstance(parsed, AnalysisResult)
    assert parsed.claim == "A claim"
    assert parsed.sources[0]["url"] == "https://a.example/source"
    assert any(source["url"] == "https://b.example/extra" for source in parsed.sources)


def test_parse_analysis_response_returns_raw_text_on_invalid_json():
    parsed = parse_analysis_response("not json", [])

    assert parsed.claim == ""
    assert parsed.raw_text == "not json"
    assert parsed.sources == []


def test_is_structured_requires_claim_and_draft_note():
    only_claim = AnalysisResult(
        claim="x", verdict="", form_misleading="", form_category="",
        form_harmful="", draft_note="", sources=[], raw_text="",
    )
    full = AnalysisResult(
        claim="x", verdict="", form_misleading="", form_category="",
        form_harmful="", draft_note="y", sources=[], raw_text="",
    )
    assert only_claim.is_structured() is False
    assert full.is_structured() is True


def test_build_revision_input_includes_prior_context():
    prior = AnalysisResult(
        claim="The claim",
        verdict="Misleading",
        form_misleading="yes",
        form_category="Factual error",
        form_harmful="no",
        draft_note="Old draft",
        sources=[{"url": "https://example.com", "description": "Example"}],
        raw_text="",
    )
    out = build_revision_input(prior, "make it shorter", "original input text")

    assert "make it shorter" in out
    assert "The claim" in out
    assert "Old draft" in out
    assert "https://example.com" in out
    assert "original input text" in out


def test_analysis_json_schema_lists_required_fields():
    required = set(ANALYSIS_JSON_SCHEMA["required"])
    assert {
        "claim",
        "verdict",
        "form_misleading",
        "form_category",
        "form_harmful",
        "draft_note",
        "sources",
    } <= required


def test_revise_calls_openai_without_tools(monkeypatch):
    """The revise() path must not pass web_search/x_search tools."""
    import asyncio

    captured_kwargs: dict = {}

    class FakeResponses:
        def create(self, **kwargs):
            captured_kwargs.update(kwargs)
            return SimpleNamespace(
                output_text=json.dumps(
                    {
                        "claim": "x",
                        "verdict": "y",
                        "form_misleading": "no",
                        "form_category": "Factual error",
                        "form_harmful": "no",
                        "draft_note": "shorter draft https://example.com",
                        "sources": [{"url": "https://example.com", "description": "Example"}],
                    }
                ),
                citations=[],
            )

    class FakeClient:
        responses = FakeResponses()

    settings = Settings(telegram_bot_token="t", xai_api_key="k")
    analyzer = XAIAnalyzer(settings)
    monkeypatch.setattr(analyzer, "_create_client", lambda: FakeClient())

    prior = AnalysisResult(
        claim="x", verdict="y", form_misleading="no", form_category="Factual error",
        form_harmful="no", draft_note="long draft", sources=[], raw_text="",
    )
    result = asyncio.run(analyzer.revise(prior, "shorter please", "original"))

    assert "tools" not in captured_kwargs or captured_kwargs.get("tools") in (None, [])
    assert result.draft_note == "shorter draft https://example.com"


def test_readme_mentions_webhook_and_vps_notes():
    text = Path("README.md").read_text(encoding="utf-8")

    assert "webhook" in text.lower()
    assert "vps" in text.lower()
