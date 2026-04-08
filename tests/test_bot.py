import asyncio
from types import SimpleNamespace

from analyzer import AnalysisResult
from bot import (
    REVISION_PRESETS,
    _get_user_lock,
    _result_from_dict,
    _send_result,
    install_webhook_health_route,
    looks_like_tweet_url,
)


def test_revision_presets_cover_all_buttons():
    assert {"shorter", "neutral", "strongest", "regenerate"} <= set(REVISION_PRESETS.keys())
    for value in REVISION_PRESETS.values():
        assert isinstance(value, str) and len(value) > 0


def test_looks_like_tweet_url_detects_x_and_twitter():
    assert looks_like_tweet_url("https://x.com/user/status/1") is True
    assert looks_like_tweet_url("https://twitter.com/user/status/1") is True
    assert looks_like_tweet_url("just a claim") is False


def test_get_user_lock_is_per_user_and_reused():
    application = SimpleNamespace(bot_data={})
    lock_a = _get_user_lock(application, 1)
    lock_b = _get_user_lock(application, 2)
    lock_a_again = _get_user_lock(application, 1)

    assert lock_a is lock_a_again
    assert lock_a is not lock_b


def test_result_from_dict_round_trip():
    data = {
        "claim": "c",
        "verdict": "v",
        "form_misleading": "yes",
        "form_category": "Factual error",
        "form_harmful": "no",
        "draft_note": "d",
        "sources": [{"url": "https://example.com", "description": "x"}],
        "raw_text": "",
    }
    result = _result_from_dict(data)
    assert isinstance(result, AnalysisResult)
    assert result.claim == "c"
    assert result.sources[0]["url"] == "https://example.com"


class _FakePlaceholder:
    def __init__(self):
        self.edits: list[dict] = []

    async def edit_text(self, text, **kwargs):
        self.edits.append({"text": text, **kwargs})


class _FakeMessage:
    def __init__(self):
        self.replies: list[dict] = []

    async def reply_text(self, text, **kwargs):
        self.replies.append({"text": text, **kwargs})


def test_send_result_single_chunk_attaches_keyboard_to_placeholder():
    placeholder = _FakePlaceholder()
    message = _FakeMessage()

    asyncio.run(_send_result(message, placeholder, "short message", attach_keyboard=True))

    assert len(placeholder.edits) == 1
    assert placeholder.edits[0]["reply_markup"] is not None
    assert message.replies == []


def test_send_result_multi_chunk_attaches_keyboard_only_to_last():
    placeholder = _FakePlaceholder()
    message = _FakeMessage()

    # Build a long text guaranteed to split into 3 chunks at the default limit (4000).
    para = "x" * 2000
    long_text = "\n\n".join([para, para, para])

    asyncio.run(_send_result(message, placeholder, long_text, attach_keyboard=True))

    # First chunk goes to placeholder without keyboard (more chunks follow).
    assert len(placeholder.edits) == 1
    assert placeholder.edits[0]["reply_markup"] is None
    # Remaining chunks go to message; only the last has the keyboard.
    assert len(message.replies) == 2
    assert message.replies[0]["reply_markup"] is None
    assert message.replies[-1]["reply_markup"] is not None


def test_install_webhook_health_route_adds_health_handler():
    import asyncio as _asyncio

    from telegram.ext._utils.webhookhandler import WebhookAppClass

    install_webhook_health_route()
    app = WebhookAppClass(
        webhook_path="/telegram",
        bot=None,  # type: ignore[arg-type]
        update_queue=_asyncio.Queue(),
        secret_token=None,
    )

    # Walk tornado's nested router tree looking for any path rule mentioning
    # "health". add_handlers() creates a sub-router under default_router.
    def _collect_patterns(rules):
        patterns = []
        for rule in rules:
            matcher = getattr(rule, "matcher", None)
            regex = getattr(matcher, "regex", None)
            if regex is not None:
                patterns.append(regex.pattern)
            target = getattr(rule, "target", None)
            sub_rules = getattr(target, "rules", None)
            if sub_rules:
                patterns.extend(_collect_patterns(sub_rules))
        return patterns

    patterns = _collect_patterns(app.default_router.rules) + _collect_patterns(
        app.wildcard_router.rules
    )
    assert any("health" in p for p in patterns), (
        f"WebhookAppClass should expose a /health route after patching; got {patterns}"
    )


def test_send_result_no_keyboard_when_parse_failure():
    placeholder = _FakePlaceholder()
    message = _FakeMessage()

    asyncio.run(_send_result(message, placeholder, "fail message", attach_keyboard=False))

    assert placeholder.edits[0]["reply_markup"] is None
