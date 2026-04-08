from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


DEFAULT_SQLITE_PATH = "community_note_copilot.sqlite3"


@dataclass(slots=True)
class Settings:
    telegram_bot_token: str
    xai_api_key: str
    xai_base_url: str = "https://api.x.ai/v1"
    xai_model: str = "grok-4.20-0309-reasoning"
    telegram_webhook_url: str | None = None
    telegram_webhook_secret: str | None = None
    telegram_listen_host: str = "0.0.0.0"
    telegram_listen_port: int = 8080
    sqlite_path: str = DEFAULT_SQLITE_PATH

    @property
    def webhook_enabled(self) -> bool:
        return bool(self.telegram_webhook_url)


def load_settings() -> Settings:
    try:
        from dotenv import load_dotenv
    except ImportError:  # pragma: no cover
        load_dotenv = None

    if load_dotenv is not None:
        load_dotenv()

    telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    xai_api_key = os.getenv("XAI_API_KEY")
    if not telegram_bot_token or not xai_api_key:
        raise ValueError("TELEGRAM_BOT_TOKEN and XAI_API_KEY are required")

    sqlite_path = os.getenv("SQLITE_PATH", DEFAULT_SQLITE_PATH)

    return Settings(
        telegram_bot_token=telegram_bot_token,
        xai_api_key=xai_api_key,
        xai_base_url=os.getenv("XAI_BASE_URL", "https://api.x.ai/v1"),
        xai_model=os.getenv("XAI_MODEL", "grok-4.20-0309-reasoning"),
        telegram_webhook_url=os.getenv("TELEGRAM_WEBHOOK_URL"),
        telegram_webhook_secret=os.getenv("TELEGRAM_WEBHOOK_SECRET"),
        telegram_listen_host=os.getenv("TELEGRAM_LISTEN_HOST", "0.0.0.0"),
        telegram_listen_port=int(os.getenv("TELEGRAM_LISTEN_PORT", "8080")),
        sqlite_path=str(Path(sqlite_path)),
    )
