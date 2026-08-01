import pytest
from pydantic import BaseModel

from easyagents.workflows.checkpoint import CheckpointManager, Checkpoint


class FakeState(BaseModel):
    query: str = "test"
    results: list[str] = []


@pytest.mark.asyncio
async def test_save_and_load_checkpoint():
    mgr = CheckpointManager()
    cp_id = await mgr.save("wf-1", "NodeA", FakeState(query="hello"))
    loaded = await mgr.load(cp_id)
    assert loaded is not None
    assert loaded.workflow_id == "wf-1"
    assert loaded.node_name == "NodeA"
    assert "hello" in str(loaded.state)


@pytest.mark.asyncio
async def test_load_nonexistent_returns_none():
    mgr = CheckpointManager()
    assert await mgr.load("nonexistent") is None


@pytest.mark.asyncio
async def test_list_checkpoints():
    mgr = CheckpointManager()
    await mgr.save("wf-1", "A", FakeState())
    await mgr.save("wf-1", "B", FakeState())
    await mgr.save("wf-2", "C", FakeState())
    ids = await mgr.list_checkpoints("wf-1")
    assert len(ids) == 2


@pytest.mark.asyncio
async def test_rollback_returns_checkpoint():
    mgr = CheckpointManager()
    cp_id = await mgr.save("wf-1", "NodeA", FakeState(query="saved"))
    loaded = await mgr.rollback(cp_id)
    assert loaded is not None
    assert loaded.checkpoint_id == cp_id


@pytest.mark.asyncio
async def test_sqlite_backend():
    from easyagents.persistence.sqlite import SQLiteSessionStore
    mgr = CheckpointManager(store=SQLiteSessionStore(":memory:"))
    cp_id = await mgr.save("wf-1", "NodeA", FakeState(query="persisted"))
    loaded = await mgr.load(cp_id)
    assert loaded is not None
    assert "persisted" in str(loaded.state)
