from bot import build_followup_input, is_followup_request
from storage import Storage


def test_save_and_load_latest_analysis(tmp_path):
    db = Storage(tmp_path / "bot.sqlite3")
    db.initialize()
    db.save_analysis(
        telegram_user_id=42,
        chat_id=99,
        user_input="tweet text",
        analysis={"claim": "x", "draft_note": "y", "sources": []},
        raw_response="{}",
    )

    latest = db.get_latest_analysis(42)

    assert latest is not None
    assert latest["analysis"]["claim"] == "x"
    assert latest["chat_id"] == 99


def test_followup_uses_latest_analysis_context(tmp_path):
    db = Storage(tmp_path / "bot.sqlite3")
    db.initialize()
    db.save_analysis(
        telegram_user_id=42,
        chat_id=99,
        user_input="tweet text",
        analysis={
            "claim": "The post claims crime rose 80%",
            "draft_note": "Available FBI data shows a different trend https://example.com/fbi",
            "sources": [{"url": "https://example.com/fbi", "description": "FBI data"}],
            "verdict": "Factually Inaccurate",
            "form_category": "Factual error",
        },
        raw_response="{}",
    )

    context = build_followup_input(db, 42, "make it shorter")

    assert "make it shorter" in context
    assert "The post claims crime rose 80%" in context
    assert "Available FBI data shows a different trend" in context


def test_followup_classifier_distinguishes_revision_from_new_claim():
    assert is_followup_request("make it shorter") is True
    assert is_followup_request("rewrite this in a more neutral tone") is True
    assert is_followup_request("The mayor said taxes fell 20%") is False
