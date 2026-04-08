import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from analyzer import AnalysisResult, extract_output_text, load_settings, parse_analysis_response


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


def test_readme_mentions_webhook_and_vps_notes():
    text = Path("README.md").read_text(encoding="utf-8")

    assert "webhook" in text.lower()
    assert "vps" in text.lower()
