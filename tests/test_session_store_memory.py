import pytest
from pydantic_ai import ModelRequest, ModelResponse, TextPart, UserPromptPart

from easyagents.core.session import Session
from easyagents.persistence.memory import InMemorySessionStore


@pytest.fixture
def store():
    return InMemorySessionStore()


def test_create_returns_session(store):
    session = store.create()
    assert isinstance(session, Session)
    assert session.conversation_id is not None
    assert session.messages == []


def test_get_existing(store):
    created = store.create()
    retrieved = store.get(created.conversation_id)
    assert retrieved is created


def test_get_nonexistent_returns_none(store):
    assert store.get("nonexistent") is None


def test_save_messages(store):
    session = store.create()
    messages = [
        ModelRequest(parts=[UserPromptPart(content="Hello")]),
        ModelResponse(parts=[TextPart(content="Hi")]),
    ]
    store.save_messages(session.conversation_id, messages)
    retrieved = store.get(session.conversation_id)
    assert retrieved.messages == messages


def test_delete(store):
    session = store.create()
    store.delete(session.conversation_id)
    assert store.get(session.conversation_id) is None


def test_list_sessions(store):
    s1 = store.create()
    s2 = store.create()
    ids = store.list_sessions()
    assert s1.conversation_id in ids
    assert s2.conversation_id in ids
    assert len(ids) == 2
