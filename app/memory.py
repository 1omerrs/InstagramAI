import sqlite3
from datetime import datetime, timezone

from app.config import get_settings


def _connect() -> sqlite3.Connection:
    settings = get_settings()
    path = settings.resolve_path(settings.database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    with _connect() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS processed_messages (
                message_id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL
            )
            """
        )


def claim_message(message_id: str) -> bool:
    """Aynı Meta mesajının ikinci kez yanıtlanmasını engeller."""
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as connection:
        try:
            connection.execute(
                "INSERT INTO processed_messages (message_id, created_at) VALUES (?, ?)",
                (message_id, now),
            )
        except sqlite3.IntegrityError:
            return False
    return True


def release_message(message_id: str) -> None:
    with _connect() as connection:
        connection.execute(
            "DELETE FROM processed_messages WHERE message_id = ?",
            (message_id,),
        )


def add_message(sender_id: str, role: str, content: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as connection:
        connection.execute(
            """
            INSERT INTO messages (sender_id, role, content, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (sender_id, role, content, now),
        )


def init_outbox() -> None:
    with _connect() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS outbox (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recipient_id TEXT NOT NULL,
                text TEXT NOT NULL,
                mode TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )


def save_outbox(recipient_id: str, text: str, mode: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    init_outbox()
    with _connect() as connection:
        connection.execute(
            """
            INSERT INTO outbox (recipient_id, text, mode, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (recipient_id, text, mode, now),
        )


def recent_outbox(limit: int = 10) -> list[dict[str, str]]:
    init_outbox()
    with _connect() as connection:
        rows = connection.execute(
            """
            SELECT recipient_id, text, mode, created_at
            FROM outbox
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [
        {
            "recipient_id": row["recipient_id"],
            "text": row["text"],
            "mode": row["mode"],
            "created_at": row["created_at"],
        }
        for row in rows
    ]


def recent_messages(sender_id: str, limit: int) -> list[dict[str, str]]:
    with _connect() as connection:
        rows = connection.execute(
            """
            SELECT role, content
            FROM messages
            WHERE sender_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (sender_id, limit),
        ).fetchall()
    ordered = list(reversed(rows))
    return [{"role": row["role"], "content": row["content"]} for row in ordered]
