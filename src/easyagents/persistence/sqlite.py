import sqlite3
from uuid import uuid4

from pydantic import TypeAdapter, ValidationError
from pydantic_ai import ModelMessage

from easyagents.core.exceptions import SessionStoreError
from easyagents.core.session import Session
from easyagents.persistence.base import SessionStore

_MESSAGE_ADAPTER = TypeAdapter(list[ModelMessage])


class SQLiteSessionStore(SessionStore):
    """SQLite-backed session store.

    Messages are serialized to JSON using Pydantic's TypeAdapter.
    Uses sync sqlite3 (local I/O is fast enough for session operations).

    A single persistent connection is held for the lifetime of the store so
    that ``:memory:`` databases survive across operations (each
    ``sqlite3.connect(":memory:")`` would otherwise create a fresh, empty DB).
    """

    def __init__(self, db_path: str = "easyagents.db") -> None:
        self._db_path = db_path
        self._conn = sqlite3.connect(self._db_path)
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._init_db()

    def _init_db(self) -> None:
        try:
            self._conn.executescript("""
                CREATE TABLE IF NOT EXISTS sessions (
                    conversation_id TEXT PRIMARY KEY,
                    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
                    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS messages (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT NOT NULL,
                    seq             INTEGER NOT NULL,
                    message_data    TEXT NOT NULL,
                    FOREIGN KEY (conversation_id) REFERENCES sessions(conversation_id)
                );

                CREATE INDEX IF NOT EXISTS idx_messages_conversation
                    ON messages(conversation_id);
            """)
            self._conn.commit()
            self._conn.execute("PRAGMA foreign_keys = ON")
        except sqlite3.Error as e:
            raise SessionStoreError(f"Failed to initialize database: {e}") from e

    def create(self) -> Session:
        conversation_id = str(uuid4())
        try:
            with self._conn:
                self._conn.execute(
                    "INSERT INTO sessions (conversation_id) VALUES (?)",
                    (conversation_id,),
                )
        except sqlite3.Error as e:
            raise SessionStoreError(f"Failed to create session: {e}") from e
        return Session(conversation_id=conversation_id)

    def get(self, conversation_id: str) -> Session | None:
        try:
            cursor = self._conn.execute(
                "SELECT conversation_id FROM sessions WHERE conversation_id = ?",
                (conversation_id,),
            )
            row = cursor.fetchone()
            if row is None:
                return None

            cursor = self._conn.execute(
                "SELECT message_data FROM messages WHERE conversation_id = ? ORDER BY seq",
                (conversation_id,),
            )
            rows = cursor.fetchall()
            if rows:
                json_str = "[" + ",".join(r[0] for r in rows) + "]"
                messages = _MESSAGE_ADAPTER.validate_json(json_str)
            else:
                messages = []

            return Session(conversation_id=conversation_id, messages=messages)
        except (sqlite3.Error, ValidationError) as e:
            raise SessionStoreError(f"Failed to get session: {e}") from e

    def save_messages(self, conversation_id: str, messages: list) -> None:
        try:
            serialized = []
            for i, msg in enumerate(messages):
                single_json = TypeAdapter(ModelMessage).dump_json(msg).decode()
                serialized.append((conversation_id, i, single_json))

            with self._conn:
                self._conn.execute(
                    "DELETE FROM messages WHERE conversation_id = ?",
                    (conversation_id,),
                )
                self._conn.executemany(
                    "INSERT INTO messages (conversation_id, seq, message_data) VALUES (?, ?, ?)",
                    serialized,
                )
                self._conn.execute(
                    "UPDATE sessions SET updated_at = datetime('now') WHERE conversation_id = ?",
                    (conversation_id,),
                )
        except sqlite3.Error as e:
            raise SessionStoreError(f"Failed to save messages: {e}") from e

    def delete(self, conversation_id: str) -> None:
        try:
            with self._conn:
                self._conn.execute(
                    "DELETE FROM messages WHERE conversation_id = ?",
                    (conversation_id,),
                )
                self._conn.execute(
                    "DELETE FROM sessions WHERE conversation_id = ?",
                    (conversation_id,),
                )
        except sqlite3.Error as e:
            raise SessionStoreError(f"Failed to delete session: {e}") from e

    def list_sessions(self) -> list[str]:
        try:
            cursor = self._conn.execute("SELECT conversation_id FROM sessions")
            return [row[0] for row in cursor.fetchall()]
        except sqlite3.Error as e:
            raise SessionStoreError(f"Failed to list sessions: {e}") from e

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self._conn.close()
