from __future__ import annotations

from dataclasses import dataclass, field

from pydantic_ai import ModelMessage

from easyagents.core.exceptions import EasyAgentsError


@dataclass
class Session:
    conversation_id: str
    messages: list[ModelMessage] = field(default_factory=list)


class SessionManager:
    """Session manager that delegates to a SessionStore backend.

    With no arguments, uses InMemorySessionStore (backward compatible with MVP).
    Pass a SessionStore instance to use a different backend (e.g. SQLiteSessionStore).
    """

    def __init__(self, store=None) -> None:
        if store is None:
            from easyagents.persistence.memory import InMemorySessionStore
            store = InMemorySessionStore()
        self._store = store

    def create(self) -> Session:
        return self._store.create()

    def get(self, conversation_id: str) -> Session | None:
        return self._store.get(conversation_id)

    def save_messages(self, conversation_id: str, messages: list[ModelMessage]) -> None:
        if self._store.get(conversation_id) is None:
            raise EasyAgentsError(f"Session '{conversation_id}' not found")
        self._store.save_messages(conversation_id, messages)

    def delete(self, conversation_id: str) -> None:
        self._store.delete(conversation_id)

    def list_sessions(self) -> list[str]:
        return self._store.list_sessions()
