from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class Storage:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = str(db_path)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def initialize(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_user_id INTEGER NOT NULL,
                    chat_id INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS analyses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_user_id INTEGER NOT NULL,
                    chat_id INTEGER NOT NULL,
                    user_input TEXT NOT NULL,
                    analysis_json TEXT NOT NULL,
                    raw_response TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )

    def save_message(self, telegram_user_id: int, chat_id: int, role: str, content: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO messages (telegram_user_id, chat_id, role, content, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (telegram_user_id, chat_id, role, content, _utcnow()),
            )

    def save_analysis(
        self,
        telegram_user_id: int,
        chat_id: int,
        user_input: str,
        analysis: dict[str, Any],
        raw_response: str,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO analyses (telegram_user_id, chat_id, user_input, analysis_json, raw_response, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    telegram_user_id,
                    chat_id,
                    user_input,
                    json.dumps(analysis),
                    raw_response,
                    _utcnow(),
                ),
            )

    def get_latest_analysis(self, telegram_user_id: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT telegram_user_id, chat_id, user_input, analysis_json, raw_response, created_at
                FROM analyses
                WHERE telegram_user_id = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (telegram_user_id,),
            ).fetchone()

        if row is None:
            return None

        return {
            "telegram_user_id": row["telegram_user_id"],
            "chat_id": row["chat_id"],
            "user_input": row["user_input"],
            "analysis": json.loads(row["analysis_json"]),
            "raw_response": row["raw_response"],
            "created_at": row["created_at"],
        }


def _utcnow() -> str:
    return datetime.now(UTC).isoformat()
