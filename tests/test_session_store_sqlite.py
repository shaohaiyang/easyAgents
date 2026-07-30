import pytest
from pydantic_ai import ModelRequest, ModelResponse, TextPart, UserPromptPart

from easyagents.core.session import Session
from easyagents.persistence.sqlite import SQLiteSessionStore


@pytest.fixture
def store():
    return SQLiteSessionStore(":memory:")


def test_create_returns_session(store):
    session = store.create()
    assert isinstance(session, Session)
    assert session.conversation_id is not None
    assert session.messages == []


def test_get_existing(store):
    created = store.create()
    retrieved = store.get(created.conversation_id)
    assert retrieved is not None
    assert retrieved.conversation_id == created.conversation_id


def test_get_nonexistent_returns_none(store):
    assert store.get("nonexistent") is None


def test_save_and_retrieve_messages(store):
    session = store.create()
    messages = [
        ModelRequest(parts=[UserPromptPart(content="Hello")]),
        ModelResponse(parts=[TextPart(content="Hi there")]),
    ]
    store.save_messages(session.conversation_id, messages)

    retrieved = store.get(session.conversation_id)
    assert len(retrieved.messages) == 2


def test_save_messages_overwrites(store):
    session = store.create()
    old = [ModelRequest(parts=[UserPromptPart(content="Old")])]
    new = [ModelRequest(parts=[UserPromptPart(content="New")])]
    store.save_messages(session.conversation_id, old)
    store.save_messages(session.conversation_id, new)

    retrieved = store.get(session.conversation_id)
    assert len(retrieved.messages) == 1


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


def test_persistence_across_instances():
    """Two store instances with the same db file see the same data."""
    import tempfile
    import os

    db_path = tempfile.mktemp(suffix=".db")
    try:
        store1 = SQLiteSessionStore(db_path)
        session = store1.create()
        messages = [ModelRequest(parts=[UserPromptPart(content="Hello")])]
        store1.save_messages(session.conversation_id, messages)

        store2 = SQLiteSessionStore(db_path)
        retrieved = store2.get(session.conversation_id)
        assert retrieved is not None
        assert len(retrieved.messages) == 1
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)
