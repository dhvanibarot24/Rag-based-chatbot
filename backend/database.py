import os
import re
import secrets
import sqlite3
from datetime import datetime, timezone
from typing import Dict, List, Optional

import bcrypt

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.getenv("SQLITE_DB_PATH", os.path.join(BASE_DIR, "chatbot.sqlite3"))
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db() -> None:
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL,
                last_login TEXT
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                session_id TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                sender TEXT NOT NULL,
                message TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES chat_sessions(session_id) ON DELETE CASCADE
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_chat_sessions_user_id ON chat_sessions(user_id)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_messages_session_id ON messages(session_id)"
        )


def validate_email(email: str) -> bool:
    return bool(EMAIL_PATTERN.match((email or "").strip()))


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def public_user(row: sqlite3.Row) -> Dict[str, object]:
    return {
        "id": row["id"],
        "full_name": row["full_name"],
        "email": row["email"],
        "created_at": row["created_at"],
        "last_login": row["last_login"],
    }


def create_user(full_name: str, email: str, password: str) -> Dict[str, object]:
    created_at = utc_now()

    with get_connection() as connection:
        try:
            cursor = connection.execute(
                """
                INSERT INTO users (full_name, email, password_hash, created_at, last_login)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    full_name.strip(),
                    normalize_email(email),
                    hash_password(password),
                    created_at,
                    created_at,
                ),
            )
        except sqlite3.IntegrityError as exc:
            raise ValueError("An account with this email already exists.") from exc

        row = connection.execute(
            "SELECT id, full_name, email, created_at, last_login FROM users WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()

    return public_user(row)


def authenticate_user(email: str, password: str) -> Optional[Dict[str, object]]:
    with get_connection() as connection:
        row = connection.execute(
            "SELECT * FROM users WHERE email = ?",
            (normalize_email(email),),
        ).fetchone()

        if row is None or not verify_password(password, row["password_hash"]):
            return None

        connection.execute(
            "UPDATE users SET last_login = ? WHERE id = ?",
            (utc_now(), row["id"]),
        )
        updated = connection.execute(
            "SELECT id, full_name, email, created_at, last_login FROM users WHERE id = ?",
            (row["id"],),
        ).fetchone()

    return public_user(updated)


def get_user_by_id(user_id: int) -> Optional[Dict[str, object]]:
    with get_connection() as connection:
        row = connection.execute(
            "SELECT id, full_name, email, created_at, last_login FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()

    return public_user(row) if row else None


def create_chat_session(user_id: int) -> str:
    session_id = secrets.token_urlsafe(24)
    with get_connection() as connection:
        connection.execute(
            "INSERT INTO chat_sessions (user_id, session_id, created_at) VALUES (?, ?, ?)",
            (user_id, session_id, utc_now()),
        )
    return session_id


def ensure_chat_session(user_id: int, session_id: Optional[str] = None) -> str:
    if session_id and user_owns_session(user_id, session_id):
        return session_id
    return create_chat_session(user_id)


def user_owns_session(user_id: int, session_id: str) -> bool:
    with get_connection() as connection:
        row = connection.execute(
            "SELECT 1 FROM chat_sessions WHERE user_id = ? AND session_id = ?",
            (user_id, session_id),
        ).fetchone()
    return row is not None


def list_chat_sessions(user_id: int) -> List[Dict[str, object]]:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                cs.session_id,
                cs.created_at,
                COUNT(m.id) AS message_count,
                MAX(m.timestamp) AS last_message_at,
                (
                    SELECT message
                    FROM messages
                    WHERE session_id = cs.session_id
                    ORDER BY id DESC
                    LIMIT 1
                ) AS last_message
            FROM chat_sessions cs
            LEFT JOIN messages m ON m.session_id = cs.session_id
            WHERE cs.user_id = ?
            GROUP BY cs.session_id, cs.created_at
            ORDER BY COALESCE(last_message_at, cs.created_at) DESC
            """,
            (user_id,),
        ).fetchall()

    return [dict(row) for row in rows]


def save_message(session_id: str, sender: str, message: str) -> None:
    with get_connection() as connection:
        connection.execute(
            "INSERT INTO messages (session_id, sender, message, timestamp) VALUES (?, ?, ?, ?)",
            (session_id, sender, message, utc_now()),
        )


def get_messages(session_id: str) -> List[Dict[str, object]]:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, session_id, sender, message, timestamp
            FROM messages
            WHERE session_id = ?
            ORDER BY id ASC
            """,
            (session_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def delete_messages(session_id: str) -> None:
    with get_connection() as connection:
        connection.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))


def recent_chat_pairs(session_id: str, limit: int = 4) -> List[Dict[str, str]]:
    messages = get_messages(session_id)
    pairs: List[Dict[str, str]] = []
    pending_question = None

    for message in messages:
        if message["sender"] == "user":
            pending_question = message["message"]
        elif message["sender"] == "assistant" and pending_question:
            pairs.append({"question": pending_question, "answer": message["message"]})
            pending_question = None

    return pairs[-limit:]
