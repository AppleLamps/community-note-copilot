from __future__ import annotations

import asyncio
import logging
from typing import Any

from analyzer import AnalysisResult, XAIAnalyzer, build_analyzer
from config import Settings, load_settings
from formatter import format_analysis_message, format_parse_failure, split_for_telegram
from storage import Storage


LOGGER = logging.getLogger(__name__)


START_TEXT = (
    "Community Note Copilot reviews tweet URLs or pasted claims, checks context, and drafts a "
    "Community Note with suggested form selections.\n\n"
    "Examples:\n"
    "- paste a tweet URL\n"
    "- paste a claim or screenshot text\n"
    "- after an analysis, use the buttons to revise (Shorter, More neutral, etc.)\n"
    "- /reset clears the current draft so the next message starts fresh"
)


REVISION_PRESETS: dict[str, str] = {
    "shorter": "Make it shorter while preserving the strongest evidence.",
    "neutral": "Rewrite it in a more neutral, encyclopedic tone.",
    "strongest": "Focus on the single strongest source and tighten the wording around it.",
    "regenerate": "Regenerate the draft from the same evidence with fresh phrasing.",
}


def _result_keyboard() -> Any:
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Shorter", callback_data="revise:shorter"),
                InlineKeyboardButton("More neutral", callback_data="revise:neutral"),
            ],
            [
                InlineKeyboardButton("Strongest source", callback_data="revise:strongest"),
                InlineKeyboardButton("Regenerate", callback_data="revise:regenerate"),
            ],
            [InlineKeyboardButton("Reset context", callback_data="reset")],
        ]
    )


def _get_user_lock(application: Any, user_id: int) -> asyncio.Lock:
    locks: dict[int, asyncio.Lock] = application.bot_data.setdefault("user_locks", {})
    lock = locks.get(user_id)
    if lock is None:
        lock = asyncio.Lock()
        locks[user_id] = lock
    return lock


async def start_command(update: Any, context: Any) -> None:
    await update.effective_message.reply_text(START_TEXT)


async def help_command(update: Any, context: Any) -> None:
    await update.effective_message.reply_text(START_TEXT)


async def reset_command(update: Any, context: Any) -> None:
    storage: Storage = context.application.bot_data["storage"]
    user_id = update.effective_user.id
    storage.clear_user_state(user_id)
    await update.effective_message.reply_text("Context cleared. Send a tweet URL or claim to start fresh.")


async def _send_result(
    message: Any,
    placeholder: Any,
    final_text: str,
    attach_keyboard: bool,
) -> None:
    from telegram.constants import ParseMode

    chunks = split_for_telegram(final_text)
    keyboard = _result_keyboard() if attach_keyboard else None

    # First chunk replaces the placeholder.
    first = chunks[0]
    await placeholder.edit_text(
        first,
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
        reply_markup=keyboard if len(chunks) == 1 else None,
    )

    # Remaining chunks: send as new messages; keyboard goes on the last one.
    for index, chunk in enumerate(chunks[1:], start=1):
        is_last = index == len(chunks) - 1
        await message.reply_text(
            chunk,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
            reply_markup=keyboard if is_last else None,
        )


async def _run_analysis(
    application: Any,
    message: Any,
    placeholder: Any,
    user_id: int,
    chat_id: int,
    request_mode: str,
    user_input_for_log: str,
    analyzer_call,
    parent_id: int | None,
) -> None:
    storage: Storage = application.bot_data["storage"]

    try:
        analysis = await analyzer_call()

        if analysis.is_structured():
            final_text = format_analysis_message(analysis, request_mode=request_mode)
            attach_keyboard = True
        else:
            final_text = format_parse_failure(analysis.raw_text)
            attach_keyboard = False

        storage.save_analysis(
            telegram_user_id=user_id,
            chat_id=chat_id,
            user_input=user_input_for_log,
            analysis=analysis.to_dict(),
            raw_response=analysis.raw_text,
            parent_id=parent_id,
        )
        storage.save_message(user_id, chat_id, "assistant", final_text)

        await _send_result(message, placeholder, final_text, attach_keyboard=attach_keyboard)
    except Exception as exc:  # pragma: no cover - network/SDK errors
        from telegram.constants import ParseMode

        LOGGER.exception("Analysis failed")
        await placeholder.edit_text(
            format_parse_failure(str(exc)),
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )


async def message_handler(update: Any, context: Any) -> None:
    message = update.effective_message
    if message is None or not message.text:
        return

    storage: Storage = context.application.bot_data["storage"]
    analyzer: XAIAnalyzer = context.application.bot_data["analyzer"]
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    incoming_text = message.text.strip()

    storage.save_message(user_id, chat_id, "user", incoming_text)

    lock = _get_user_lock(context.application, user_id)
    if lock.locked():
        await message.reply_text("Still working on your previous request — one moment.")
        return

    placeholder = await message.reply_text("Analyzing... this can take ~30 seconds.")

    async with lock:
        await _run_analysis(
            application=context.application,
            message=message,
            placeholder=placeholder,
            user_id=user_id,
            chat_id=chat_id,
            request_mode="analysis",
            user_input_for_log=incoming_text,
            analyzer_call=lambda: analyzer.analyze(incoming_text),
            parent_id=None,
        )


async def callback_handler(update: Any, context: Any) -> None:
    query = update.callback_query
    if query is None or query.data is None:
        return

    storage: Storage = context.application.bot_data["storage"]
    analyzer: XAIAnalyzer = context.application.bot_data["analyzer"]
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    data: str = query.data

    await query.answer()

    if data == "reset":
        storage.clear_user_state(user_id)
        await query.edit_message_reply_markup(reply_markup=None)
        await context.bot.send_message(chat_id=chat_id, text="Context cleared.")
        return

    if not data.startswith("revise:"):
        return

    preset_key = data.split(":", 1)[1]
    followup_text = REVISION_PRESETS.get(preset_key)
    if followup_text is None:
        return

    latest = storage.get_latest_analysis(user_id)
    if latest is None:
        await context.bot.send_message(
            chat_id=chat_id,
            text="No prior analysis to revise. Send a tweet URL or claim first.",
        )
        return

    lock = _get_user_lock(context.application, user_id)
    if lock.locked():
        await context.bot.send_message(
            chat_id=chat_id,
            text="Still working on your previous request — one moment.",
        )
        return

    storage.save_message(user_id, chat_id, "user", f"[button] {followup_text}")
    placeholder = await context.bot.send_message(chat_id=chat_id, text="Revising the draft...")

    prior = _result_from_dict(latest["analysis"])
    parent_id = latest.get("id")
    original_input = latest.get("user_input", "")

    async with lock:
        await _run_analysis(
            application=context.application,
            message=placeholder,
            placeholder=placeholder,
            user_id=user_id,
            chat_id=chat_id,
            request_mode="revision",
            user_input_for_log=f"[button:{preset_key}] {followup_text}",
            analyzer_call=lambda: analyzer.revise(prior, followup_text, original_input),
            parent_id=parent_id,
        )


def _result_from_dict(data: dict[str, Any]) -> AnalysisResult:
    return AnalysisResult(
        claim=str(data.get("claim", "")),
        verdict=str(data.get("verdict", "")),
        form_misleading=str(data.get("form_misleading", "")),
        form_category=str(data.get("form_category", "")),
        form_harmful=str(data.get("form_harmful", "")),
        draft_note=str(data.get("draft_note", "")),
        sources=list(data.get("sources", []) or []),
        raw_text=str(data.get("raw_text", "")),
    )


def looks_like_tweet_url(text: str) -> bool:
    lowered = text.lower()
    return "x.com/" in lowered or "twitter.com/" in lowered


async def _start_health_server(port: int) -> None:
    """Run a tiny aiohttp server returning 200 on /health (polling mode only)."""
    try:
        from aiohttp import web
    except ImportError:  # pragma: no cover
        LOGGER.warning("aiohttp not installed, skipping /health endpoint")
        return

    async def health(_request: Any) -> Any:
        return web.Response(text="ok")

    app = web.Application()
    app.router.add_get("/health", health)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    LOGGER.info("Health endpoint listening on :%d/health", port)


_HEALTH_INSTALLED = False


def install_webhook_health_route() -> None:
    """Patch PTB's tornado WebhookAppClass to also serve GET /health.

    PTB's webhook server is a tornado.web.Application built in
    telegram.ext._utils.webhookhandler.WebhookAppClass. We wrap its __init__ so
    every instance also registers a /health route, which lets Fly.io perform
    HTTP health checks against the same port that Telegram POSTs to.
    """
    global _HEALTH_INSTALLED
    if _HEALTH_INSTALLED:
        return

    try:
        import tornado.web
        from telegram.ext._utils import webhookhandler
    except ImportError:  # pragma: no cover
        LOGGER.warning("Could not patch PTB webhook app for /health")
        return

    class _HealthHandler(tornado.web.RequestHandler):
        SUPPORTED_METHODS = ("GET",)  # type: ignore[assignment]

        def set_default_headers(self) -> None:
            self.set_header("Content-Type", "text/plain; charset=utf-8")

        async def get(self) -> None:
            self.set_status(200)
            self.write("ok")

        def log_exception(self, typ, value, tb) -> None:  # noqa: D401
            """Silence default logging on health-check errors."""

    original_init = webhookhandler.WebhookAppClass.__init__

    def patched_init(self: Any, *args: Any, **kwargs: Any) -> None:
        original_init(self, *args, **kwargs)
        self.add_handlers(r".*", [(r"/health/?", _HealthHandler)])

    webhookhandler.WebhookAppClass.__init__ = patched_init  # type: ignore[method-assign]
    _HEALTH_INSTALLED = True
    LOGGER.info("Patched PTB webhook app to serve GET /health")


async def _post_init(application: Any) -> None:
    settings: Settings = application.bot_data["settings"]
    # In polling mode there's no webhook server, so spin up a tiny aiohttp /health.
    # In webhook mode the route is mounted on PTB's tornado app via
    # install_webhook_health_route() before run_webhook starts.
    if not settings.webhook_enabled:
        await _start_health_server(settings.telegram_listen_port)


def create_application(
    settings: Settings | None = None,
    analyzer: XAIAnalyzer | None = None,
    storage: Storage | None = None,
) -> Any:
    settings = settings or load_settings()
    storage = storage or Storage(settings.sqlite_path)
    storage.initialize()
    analyzer = analyzer or build_analyzer(settings)

    from telegram.ext import (
        Application,
        CallbackQueryHandler,
        CommandHandler,
        MessageHandler,
        filters,
    )

    app = Application.builder().token(settings.telegram_bot_token).post_init(_post_init).build()
    app.bot_data["settings"] = settings
    app.bot_data["storage"] = storage
    app.bot_data["analyzer"] = analyzer
    app.bot_data["user_locks"] = {}

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("reset", reset_command))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    return app


def run() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    settings = load_settings()
    app = create_application(settings=settings)

    if settings.webhook_enabled:
        install_webhook_health_route()
        app.run_webhook(
            listen=settings.telegram_listen_host,
            port=settings.telegram_listen_port,
            webhook_url=settings.telegram_webhook_url,
            secret_token=settings.telegram_webhook_secret,
            allowed_updates=None,
        )
    else:
        app.run_polling(allowed_updates=None)


if __name__ == "__main__":  # pragma: no cover
    run()
