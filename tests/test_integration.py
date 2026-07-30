import pytest
from pydantic import BaseModel
from pydantic_ai.models.function import FunctionModel, AgentInfo
from pydantic_ai import ModelResponse, TextPart

from easyagents import (
    AgentDefinition,
    AgentRegistry,
    ToolRegistry,
    web_search,
)


class ResearchFindings(BaseModel):
    products: list[str]
    summary: str


@pytest.fixture
def handler():
    def handle(messages: list, info: AgentInfo) -> ModelResponse:
        return ModelResponse(parts=[TextPart(
            content='{"products": ["AirPods Pro 2", "Sony WF-1000XM5", "Bose QC Ultra"], "summary": "Three top competitors in the high-end TWS market."}'
        )])
    return FunctionModel(handle)


@pytest.mark.asyncio
async def test_bluetooth_earphone_research(handler):
    """End-to-end test: orchestrator delegates to researcher via delegation."""

    tools = ToolRegistry()
    tools.register("web_search", web_search)

    agents = AgentRegistry()

    agents.register(AgentDefinition(
        name="researcher",
        instructions="You are a product researcher. Use web_search to research.",
        model="test",
        tools=["web_search"],
        output_type=ResearchFindings,
        description="Product researcher",
    ))

    agents.register(AgentDefinition(
        name="orchestrator",
        instructions="You are a research orchestrator. Use delegate_researcher to delegate.",
        model="test",
        subagents=["researcher"],
        description="Research orchestrator",
    ))

    agent = agents.create("orchestrator", tools)
    result = await agent.run(
        "调研最近爆火的蓝牙耳机",
        model=handler,
    )
    assert result.output is not None


def test_full_pipeline():
    """Simplified pipeline test: register, create, and run with TestModel."""
    from pydantic_ai.models.test import TestModel

    tools = ToolRegistry()
    tools.register("web_search", lambda q: [{"title": "X", "url": "https://x.com", "snippet": "test"}])

    agents = AgentRegistry()
    agents.register(AgentDefinition(
        name="researcher",
        instructions="Research.",
        model="test",
        tools=["web_search"],
        output_type=ResearchFindings,
    ))
    agents.register(AgentDefinition(
        name="orchestrator",
        instructions="Delegate.",
        model="test",
        subagents=["researcher"],
    ))

    agent = agents.create("orchestrator", tools)
    result = agent.run_sync("research bluetooth earphones", model=TestModel())
    assert isinstance(result.output, str)
    assert len(result.output) > 0
    assert len(result.all_messages()) > 0


@pytest.mark.asyncio
async def test_sqlite_persistence_integration():
    """Test SQLite session store with agent run."""
    from easyagents import SQLiteSessionStore, SessionManager
    from pydantic_ai.models.test import TestModel

    store = SQLiteSessionStore(":memory:")
    sessions = SessionManager(store)

    session = sessions.create()
    assert sessions.get(session.conversation_id) is not None

    # Simulate saving messages from an agent run
    from pydantic_ai import ModelRequest, ModelResponse, TextPart, UserPromptPart
    messages = [
        ModelRequest(parts=[UserPromptPart(content="Hello")]),
        ModelResponse(parts=[TextPart(content="Hi there")]),
    ]
    sessions.save_messages(session.conversation_id, messages)

    # Verify retrieval
    retrieved = sessions.get(session.conversation_id)
    assert len(retrieved.messages) == 2

    # Verify list and delete
    assert len(sessions.list_sessions()) == 1
    sessions.delete(session.conversation_id)
    assert sessions.get(session.conversation_id) is None


@pytest.mark.asyncio
async def test_context_compression_integration():
    """Test ContextManager compresses a long conversation."""
    from easyagents import ContextManager
    from pydantic_ai import ModelRequest, ModelResponse, TextPart, UserPromptPart
    from pydantic_ai.models.function import FunctionModel, AgentInfo
    from pydantic_ai import ModelResponse as MR, TextPart as TP

    def handler(messages, info: AgentInfo) -> MR:
        return MR(parts=[TP(content="Summary: discussed bluetooth earphones")])

    ctx = ContextManager(model="test", max_tokens=100, keep_recent=2)

    # Create a long conversation
    long_messages = []
    for i in range(10):
        long_messages.append(ModelRequest(parts=[UserPromptPart(content=f"Question {i}" * 50)]))
        long_messages.append(ModelResponse(parts=[TextPart(content=f"Answer {i}" * 50)]))

    result = await ctx.compress_if_needed(long_messages, model=FunctionModel(handler))

    assert len(result) == 3  # 1 summary + 2 recent
    assert result[-2:] == long_messages[-2:]


def test_new_tools_registered():
    """Test http_request and write_file can be registered in ToolRegistry."""
    from easyagents import ToolRegistry, http_request, write_file

    tools = ToolRegistry()
    tools.register("http_request", http_request)
    tools.register("write_file", write_file)

    assert len(tools.list()) == 2
