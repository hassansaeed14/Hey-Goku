from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any


MEMORY_DIR = Path(__file__).resolve().parent
DB_PATH = MEMORY_DIR / "aura_history.db"
LEGACY_CHAT_JSON = MEMORY_DIR / "chat_history.json"


def _connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH, timeout=5)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=MEMORY")
    connection.execute("PRAGMA synchronous=NORMAL")
    connection.execute("PRAGMA temp_store=MEMORY")
    return connection


def _normalize_session_id(session_id: str | None) -> str:
    value = str(session_id or "").strip()
    return value[:120] if value else "default"


def _normalize_role(role: str | None) -> str:
    return "user" if str(role or "").strip().lower() == "user" else "assistant"


def _timestamp() -> str:
    return datetime.now().isoformat(sep=" ", timespec="seconds")


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": int(row["id"]),
        "session_id": row["session_id"],
        "role": row["role"],
        "message": row["message"],
        "intent": row["intent"],
        "agent_used": row["agent_used"],
        "mode": row["mode"],
        "timestamp": row["timestamp"],
    }


def _migrate_legacy_json_if_needed(connection: sqlite3.Connection) -> None:
    count = connection.execute("SELECT COUNT(*) AS total FROM chat_history").fetchone()["total"]
    if count or not LEGACY_CHAT_JSON.exists():
        return

    try:
        legacy_payload = json.loads(LEGACY_CHAT_JSON.read_text(encoding="utf-8"))
    except Exception:
        return

    if not isinstance(legacy_payload, list):
        return

    rows: list[tuple[str, str, str, str | None, str | None, str | None, str]] = []
    for item in legacy_payload:
        if not isinstance(item, dict):
            continue
        timestamp = str(item.get("time") or _timestamp())
        user_text = str(item.get("user") or "").strip()
        aura_text = str(item.get("aura") or "").strip()

        if user_text:
            rows.append(("default", "user", user_text, None, None, "legacy", timestamp))
        if aura_text:
            rows.append(("default", "assistant", aura_text, None, "legacy", "legacy", timestamp))

    if rows:
        connection.executemany(
            """
            INSERT INTO chat_history (
                session_id,
                role,
                message,
                intent,
                agent_used,
                mode,
                timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        connection.commit()


def _recover_history_store() -> bool:
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    candidates = [DB_PATH, Path(f"{DB_PATH}-journal")]
    recovered_any = False

    for candidate in candidates:
        if not candidate.exists():
            continue
        try:
            candidate.replace(candidate.with_name(f"{candidate.name}.corrupt.{timestamp}"))
            recovered_any = True
        except Exception:
            return False

    return recovered_any


def init_db() -> None:
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    try:
        with _connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS chat_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    message TEXT NOT NULL,
                    intent TEXT,
                    agent_used TEXT,
                    mode TEXT,
                    timestamp TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_chat_history_session_id ON chat_history(session_id)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_chat_history_timestamp ON chat_history(timestamp)"
            )
            _migrate_legacy_json_if_needed(connection)
    except sqlite3.OperationalError as error:
        if "disk i/o error" not in str(error).lower():
            raise
        if not _recover_history_store():
            raise
        with _connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS chat_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    message TEXT NOT NULL,
                    intent TEXT,
                    agent_used TEXT,
                    mode TEXT,
                    timestamp TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_chat_history_session_id ON chat_history(session_id)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_chat_history_timestamp ON chat_history(timestamp)"
            )
            _migrate_legacy_json_if_needed(connection)


def save_message(
    session_id: str,
    role: str,
    message: str,
    intent: str | None = None,
    agent_used: str | None = None,
    mode: str | None = None,
) -> dict[str, Any]:
    init_db()

    normalized_session = _normalize_session_id(session_id)
    normalized_role = _normalize_role(role)
    normalized_message = str(message or "").strip()
    if not normalized_message:
        raise ValueError("message is required")

    record = (
        normalized_session,
        normalized_role,
        normalized_message,
        str(intent).strip() if intent else None,
        str(agent_used).strip() if agent_used else None,
        str(mode).strip() if mode else None,
        _timestamp(),
    )

    with _connect() as connection:
        cursor = connection.execute(
            """
            INSERT INTO chat_history (
                session_id,
                role,
                message,
                intent,
                agent_used,
                mode,
                timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            record,
        )
        row = connection.execute(
            "SELECT * FROM chat_history WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()

    return _row_to_dict(row)


def get_history(session_id: str, limit: int = 50) -> list[dict[str, Any]]:
    init_db()

    normalized_session = _normalize_session_id(session_id)
    normalized_limit = max(1, min(int(limit or 50), 500))

    with _connect() as connection:
        rows = connection.execute(
            """
            SELECT *
            FROM (
                SELECT *
                FROM chat_history
                WHERE session_id = ?
                ORDER BY id DESC
                LIMIT ?
            )
            ORDER BY id ASC
            """,
            (normalized_session, normalized_limit),
        ).fetchall()

    return [_row_to_dict(row) for row in rows]


def clear_history(session_id: str) -> int:
    init_db()

    normalized_session = _normalize_session_id(session_id)
    with _connect() as connection:
        cursor = connection.execute(
            "DELETE FROM chat_history WHERE session_id = ?",
            (normalized_session,),
        )
        connection.commit()
        return int(cursor.rowcount or 0)


def get_all_sessions() -> list[dict[str, Any]]:
    init_db()

    with _connect() as connection:
        rows = connection.execute(
            """
            SELECT
                session_id,
                MIN(timestamp) AS started_at,
                MAX(timestamp) AS last_timestamp,
                COUNT(*) AS message_count
            FROM chat_history
            GROUP BY session_id
            ORDER BY last_timestamp DESC, session_id DESC
            """
        ).fetchall()

    return [
        {
            "session_id": row["session_id"],
            "started_at": row["started_at"],
            "last_timestamp": row["last_timestamp"],
            "message_count": int(row["message_count"] or 0),
        }
        for row in rows
    ]
