from __future__ import annotations

import json
import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class Storage:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = str(db_path)
        self._connection: sqlite3.Connection | None = None
        self._lock = threading.Lock()

    def _connect(self) -> sqlite3.Connection:
        # Kept for backwards compatibility with tests; returns the persistent connection.
        if self._connection is None:
            self._connection = sqlite3.connect(self.db_path, check_same_thread=False)
            self._connection.row_factory = sqlite3.Row
        return self._connection

    def initialize(self) -> None:
        conn = self._connect()
        with self._lock:
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

                CREATE TABLE IF NOT EXISTS user_state (
                    telegram_user_id INTEGER PRIMARY KEY,
                    last_cleared_id INTEGER NOT NULL DEFAULT 0
                );

                CREATE INDEX IF NOT EXISTS idx_analyses_user_id
                    ON analyses(telegram_user_id, id DESC);
                CREATE INDEX IF NOT EXISTS idx_messages_user_id
                    ON messages(telegram_user_id, id DESC);
                """
            )
            # Add parent_id column if missing (cheap migration).
            cols = {row[1] for row in conn.execute("PRAGMA table_info(analyses)").fetchall()}
            if "parent_id" not in cols:
                conn.execute("ALTER TABLE analyses ADD COLUMN parent_id INTEGER")
            conn.commit()

    def save_message(self, telegram_user_id: int, chat_id: int, role: str, content: str) -> None:
        conn = self._connect()
        with self._lock:
            conn.execute(
                """
                INSERT INTO messages (telegram_user_id, chat_id, role, content, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (telegram_user_id, chat_id, role, content, _utcnow()),
            )
            conn.commit()

    def save_analysis(
        self,
        telegram_user_id: int,
        chat_id: int,
        user_input: str,
        analysis: dict[str, Any],
        raw_response: str,
        parent_id: int | None = None,
    ) -> int:
        conn = self._connect()
        with self._lock:
            cursor = conn.execute(
                """
                INSERT INTO analyses (telegram_user_id, chat_id, user_input, analysis_json, raw_response, created_at, parent_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    telegram_user_id,
                    chat_id,
                    user_input,
                    json.dumps(analysis),
                    raw_response,
                    _utcnow(),
                    parent_id,
                ),
            )
            conn.commit()
            return int(cursor.lastrowid or 0)

    def _last_cleared_id(self, telegram_user_id: int) -> int:
        conn = self._connect()
        row = conn.execute(
            "SELECT last_cleared_id FROM user_state WHERE telegram_user_id = ?",
            (telegram_user_id,),
        ).fetchone()
        return int(row["last_cleared_id"]) if row else 0

    def get_latest_analysis(self, telegram_user_id: int) -> dict[str, Any] | None:
        conn = self._connect()
        cleared = self._last_cleared_id(telegram_user_id)
        row = conn.execute(
            """
            SELECT id, telegram_user_id, chat_id, user_input, analysis_json, raw_response, created_at, parent_id
            FROM analyses
            WHERE telegram_user_id = ? AND id > ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (telegram_user_id, cleared),
        ).fetchone()

        if row is None:
            return None

        return {
            "id": row["id"],
            "telegram_user_id": row["telegram_user_id"],
            "chat_id": row["chat_id"],
            "user_input": row["user_input"],
            "analysis": json.loads(row["analysis_json"]),
            "raw_response": row["raw_response"],
            "created_at": row["created_at"],
            "parent_id": row["parent_id"],
        }

    def clear_user_state(self, telegram_user_id: int) -> None:
        conn = self._connect()
        with self._lock:
            row = conn.execute(
                "SELECT COALESCE(MAX(id), 0) AS max_id FROM analyses WHERE telegram_user_id = ?",
                (telegram_user_id,),
            ).fetchone()
            max_id = int(row["max_id"]) if row else 0
            conn.execute(
                """
                INSERT INTO user_state (telegram_user_id, last_cleared_id)
                VALUES (?, ?)
                ON CONFLICT(telegram_user_id) DO UPDATE SET last_cleared_id = excluded.last_cleared_id
                """,
                (telegram_user_id, max_id),
            )
            conn.commit()


def _utcnow() -> str:
    return datetime.now(UTC).isoformat()
