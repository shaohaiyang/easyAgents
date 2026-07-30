import pytest
from easyagents.core.session import Session, SessionManager


@pytest.fixture
def manager():
    return SessionManager()


def test_create_session(manager):
    session = manager.create()
    assert isinstance(session, Session)
    assert session.conversation_id is not None
    assert session.messages == []


def test_get_existing_session(manager):
    created = manager.create()
    retrieved = manager.get(created.conversation_id)
    assert retrieved is created


def test_get_nonexistent_returns_none(manager):
    assert manager.get("nonexistent-id") is None


def test_save_messages(manager):
    from pydantic_ai import ModelRequest, ModelResponse, TextPart, UserPromptPart
    session = manager.create()
    messages = [
        ModelRequest(parts=[UserPromptPart(content="Hello")]),
        ModelResponse(parts=[TextPart(content="Hi")]),
    ]
    manager.save_messages(session.conversation_id, messages)
    assert session.messages == messages


def test_save_messages_overwrites(manager):
    from pydantic_ai import ModelRequest, UserPromptPart
    session = manager.create()
    old = [ModelRequest(parts=[UserPromptPart(content="Old")])]
    new = [ModelRequest(parts=[UserPromptPart(content="New")])]
    manager.save_messages(session.conversation_id, old)
    manager.save_messages(session.conversation_id, new)
    assert session.messages == new
