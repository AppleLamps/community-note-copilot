from bot import START_TEXT
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
    assert latest["id"] >= 1


def test_save_analysis_returns_id_and_supports_parent_chain(tmp_path):
    db = Storage(tmp_path / "bot.sqlite3")
    db.initialize()
    parent_id = db.save_analysis(
        telegram_user_id=7,
        chat_id=1,
        user_input="claim",
        analysis={"claim": "first", "draft_note": "n", "sources": []},
        raw_response="{}",
    )
    child_id = db.save_analysis(
        telegram_user_id=7,
        chat_id=1,
        user_input="revision",
        analysis={"claim": "first", "draft_note": "n2", "sources": []},
        raw_response="{}",
        parent_id=parent_id,
    )

    assert parent_id >= 1
    assert child_id > parent_id

    latest = db.get_latest_analysis(7)
    assert latest is not None
    assert latest["parent_id"] == parent_id


def test_clear_user_state_hides_prior_analysis(tmp_path):
    db = Storage(tmp_path / "bot.sqlite3")
    db.initialize()
    db.save_analysis(
        telegram_user_id=11,
        chat_id=1,
        user_input="claim",
        analysis={"claim": "x", "draft_note": "y", "sources": []},
        raw_response="{}",
    )

    db.clear_user_state(11)

    assert db.get_latest_analysis(11) is None

    db.save_analysis(
        telegram_user_id=11,
        chat_id=1,
        user_input="new claim",
        analysis={"claim": "fresh", "draft_note": "z", "sources": []},
        raw_response="{}",
    )
    latest = db.get_latest_analysis(11)
    assert latest is not None
    assert latest["analysis"]["claim"] == "fresh"


def test_initialize_creates_user_index(tmp_path):
    db = Storage(tmp_path / "bot.sqlite3")
    db.initialize()
    conn = db._connect()
    indexes = {row[1] for row in conn.execute("PRAGMA index_list('analyses')").fetchall()}
    assert "idx_analyses_user_id" in indexes


def test_start_text_includes_examples():
    assert "Examples:" in START_TEXT
    assert "paste a tweet URL" in START_TEXT
    assert "/reset" in START_TEXT
