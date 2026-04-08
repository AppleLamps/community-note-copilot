from __future__ import annotations

import logging
from typing import Any

from analyzer import AnalysisResult, XAIAnalyzer, build_analyzer
from config import Settings, load_settings
from formatter import format_analysis_message, format_parse_failure
from storage import Storage


LOGGER = logging.getLogger(__name__)


START_TEXT = (
    "Community Note Copilot analyzes tweet URLs or pasted claim text and drafts a Community Note "
    "with suggested X form selections. Send a tweet link, tweet text, or a follow-up revision like "
    "'make it shorter'."
)

FOLLOWUP_PREFIXES = (
    "make it ",
    "rewrite",
    "revise",
    "shorten",
    "trim",
    "condense",
    "make this",
    "make that",
    "reword",
    "tighten",
    "improve the note",
    "change the note",
)


def build_followup_input(storage: Storage, telegram_user_id: int, followup_text: str) -> str:
    latest = storage.get_latest_analysis(telegram_user_id)
    if latest is None:
        return followup_text

    analysis = latest["analysis"]
    sources = analysis.get("sources", [])
    source_lines = "\n".join(f'- {item.get("url", "")}' for item in sources) or "- none"
    return (
        "Revise the previously drafted Community Note.\n\n"
        f"Original user input:\n{latest['user_input']}\n\n"
        f"Claim:\n{analysis.get('claim', '')}\n\n"
        f"Verdict:\n{analysis.get('verdict', '')}\n\n"
        f"Current draft note:\n{analysis.get('draft_note', '')}\n\n"
        f"Current category:\n{analysis.get('form_category', '')}\n\n"
        f"Sources:\n{source_lines}\n\n"
        f"User follow-up request:\n{followup_text}"
    )


async def start_command(update: Any, context: Any) -> None:
    await update.effective_message.reply_text(START_TEXT)


async def help_command(update: Any, context: Any) -> None:
    await update.effective_message.reply_text(START_TEXT)


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

    placeholder = await message.reply_text("🔍 Analyzing…")

    try:
        latest = storage.get_latest_analysis(user_id)
        if latest and is_followup_request(incoming_text):
            analysis = await analyzer.revise(build_followup_input(storage, user_id, incoming_text))
        else:
            analysis = await analyzer.analyze(incoming_text)

        final_text = (
            format_analysis_message(analysis)
            if analysis.is_structured()
            else format_parse_failure(analysis.raw_text)
        )

        storage.save_analysis(
            telegram_user_id=user_id,
            chat_id=chat_id,
            user_input=incoming_text,
            analysis=analysis.to_dict(),
            raw_response=analysis.raw_text,
        )
        storage.save_message(user_id, chat_id, "assistant", final_text)

        await placeholder.edit_text(final_text, parse_mode="MarkdownV2", disable_web_page_preview=True)
    except Exception as exc:  # pragma: no cover
        LOGGER.exception("Analysis failed")
        await placeholder.edit_text(f"Analysis failed: {exc}")


def looks_like_tweet_url(text: str) -> bool:
    lowered = text.lower()
    return "x.com/" in lowered or "twitter.com/" in lowered


def is_followup_request(text: str) -> bool:
    lowered = text.strip().lower()
    return lowered.startswith(FOLLOWUP_PREFIXES)


def create_application(
    settings: Settings | None = None,
    analyzer: XAIAnalyzer | None = None,
    storage: Storage | None = None,
) -> Any:
    settings = settings or load_settings()
    storage = storage or Storage(settings.sqlite_path)
    storage.initialize()
    analyzer = analyzer or build_analyzer(settings)

    from telegram.ext import Application, CommandHandler, MessageHandler, filters

    app = Application.builder().token(settings.telegram_bot_token).build()
    app.bot_data["storage"] = storage
    app.bot_data["analyzer"] = analyzer

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    return app


def run() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    settings = load_settings()
    app = create_application(settings=settings)

    if settings.webhook_enabled:
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
