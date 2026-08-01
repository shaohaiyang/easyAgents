from __future__ import annotations

import datetime
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from pydantic import TypeAdapter


@dataclass
class Checkpoint:
    """A snapshot of graph state at a node, for rollback and recovery."""

    checkpoint_id: str
    workflow_id: str
    node_name: str
    state: Any
    timestamp: str


class CheckpointManager:
    """Manages graph state checkpoints for rollback and recovery.

    Supports an in-memory backend by default and a SQLite backend when
    passed a store exposing a ``_conn`` ``sqlite3.Connection`` (e.g. an
    :class:`SQLiteSessionStore`), reusing that connection so checkpoints
    share the same database lifetime.
    """

    def __init__(self, store: Any = None) -> None:
        self._store = store
        self._memory: dict[str, Checkpoint] = {}
        self._init_db()

    def _init_db(self) -> None:
        if self._store is None:
            return
        conn = getattr(self._store, "_conn", None)
        if conn is not None:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS checkpoints (
                    checkpoint_id  TEXT PRIMARY KEY,
                    workflow_id    TEXT NOT NULL,
                    node_name      TEXT NOT NULL,
                    state_data     TEXT NOT NULL,
                    timestamp      TEXT NOT NULL DEFAULT (datetime('now'))
                );
            """)

    async def save(self, workflow_id: str, node_name: str, state: Any) -> str:
        checkpoint_id = str(uuid4())
        state_data = TypeAdapter(Any).dump_json(state).decode()
        timestamp = datetime.datetime.now().isoformat()

        if self._store is not None:
            conn = getattr(self._store, "_conn", None)
            if conn is not None:
                with conn:
                    conn.execute(
                        "INSERT INTO checkpoints "
                        "(checkpoint_id, workflow_id, node_name, state_data, timestamp) "
                        "VALUES (?, ?, ?, ?, ?)",
                        (checkpoint_id, workflow_id, node_name, state_data, timestamp),
                    )
                return checkpoint_id

        cp = Checkpoint(
            checkpoint_id=checkpoint_id,
            workflow_id=workflow_id,
            node_name=node_name,
            state=state,
            timestamp=timestamp,
        )
        self._memory[checkpoint_id] = cp
        return checkpoint_id

    async def load(self, checkpoint_id: str) -> Checkpoint | None:
        if self._store is not None:
            conn = getattr(self._store, "_conn", None)
            if conn is not None:
                cursor = conn.execute(
                    "SELECT checkpoint_id, workflow_id, node_name, state_data, timestamp "
                    "FROM checkpoints WHERE checkpoint_id = ?",
                    (checkpoint_id,),
                )
                row = cursor.fetchone()
                if row is None:
                    return None
                state = TypeAdapter(Any).validate_json(row[3])
                return Checkpoint(
                    checkpoint_id=row[0],
                    workflow_id=row[1],
                    node_name=row[2],
                    state=state,
                    timestamp=row[4],
                )

        return self._memory.get(checkpoint_id)

    async def list_checkpoints(self, workflow_id: str) -> list[str]:
        if self._store is not None:
            conn = getattr(self._store, "_conn", None)
            if conn is not None:
                cursor = conn.execute(
                    "SELECT checkpoint_id FROM checkpoints "
                    "WHERE workflow_id = ? ORDER BY timestamp",
                    (workflow_id,),
                )
                return [row[0] for row in cursor.fetchall()]

        return [
            cp_id for cp_id, cp in self._memory.items()
            if cp.workflow_id == workflow_id
        ]

    async def rollback(self, checkpoint_id: str) -> Checkpoint | None:
        return await self.load(checkpoint_id)
