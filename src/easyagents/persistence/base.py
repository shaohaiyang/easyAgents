from __future__ import annotations

from abc import ABC, abstractmethod


class SessionStore(ABC):
    """Abstract base class for session storage backends."""

    @abstractmethod
    def create(self) -> Session:
        """Create a new session with a generated conversation_id."""

    @abstractmethod
    def get(self, conversation_id: str) -> Session | None:
        """Retrieve a session by conversation_id. Returns None if not found."""

    @abstractmethod
    def save_messages(self, conversation_id: str, messages: list) -> None:
        """Save messages for a session. Overwrites existing messages."""

    @abstractmethod
    def delete(self, conversation_id: str) -> None:
        """Delete a session and all its messages."""

    @abstractmethod
    def list_sessions(self) -> list[str]:
        """List all conversation_ids."""
