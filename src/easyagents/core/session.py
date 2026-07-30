from dataclasses import dataclass, field
from uuid import uuid4

from pydantic_ai import ModelMessage


@dataclass
class Session:
    conversation_id: str
    messages: list[ModelMessage] = field(default_factory=list)


class SessionManager:
    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}

    def create(self) -> Session:
        conversation_id = str(uuid4())
        session = Session(conversation_id=conversation_id)
        self._sessions[conversation_id] = session
        return session

    def get(self, conversation_id: str) -> Session | None:
        return self._sessions.get(conversation_id)

    def save_messages(self, conversation_id: str, messages: list[ModelMessage]) -> None:
        self._sessions[conversation_id].messages = messages
