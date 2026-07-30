from uuid import uuid4

from easyagents.core.session import Session
from easyagents.persistence.base import SessionStore


class InMemorySessionStore(SessionStore):
    """In-memory session store using a dict."""

    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}

    def create(self) -> Session:
        conversation_id = str(uuid4())
        session = Session(conversation_id=conversation_id)
        self._sessions[conversation_id] = session
        return session

    def get(self, conversation_id: str) -> Session | None:
        return self._sessions.get(conversation_id)

    def save_messages(self, conversation_id: str, messages: list) -> None:
        self._sessions[conversation_id].messages = messages

    def delete(self, conversation_id: str) -> None:
        self._sessions.pop(conversation_id, None)

    def list_sessions(self) -> list[str]:
        return list(self._sessions.keys())
