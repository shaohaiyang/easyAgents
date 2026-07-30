import pytest
from pydantic_ai import Agent
from easyagents.core.agent import AgentDefinition, AgentRegistry
from easyagents.core.exceptions import AgentAlreadyRegisteredError, AgentNotFoundError
from easyagents.tools.registry import ToolRegistry


@pytest.fixture
def tool_registry():
    tr = ToolRegistry()

    def dummy_tool(x: int) -> str:
        """A dummy tool for testing."""
        return str(x)

    tr.register("dummy_tool", dummy_tool)
    return tr


@pytest.fixture
def registry():
    return AgentRegistry()


def test_register_and_list(registry):
    registry.register(AgentDefinition(
        name="test_agent", instructions="You are a test agent.", model="openai:gpt-4o",
    ))
    names = registry.list()
    assert "test_agent" in names


def test_register_duplicate_raises(registry):
    registry.register(AgentDefinition(name="dup", instructions="", model="openai:gpt-4o"))
    with pytest.raises(AgentAlreadyRegisteredError):
        registry.register(AgentDefinition(name="dup", instructions="", model="openai:gpt-4o"))


def test_get_returns_definition(registry):
    expected = AgentDefinition(name="get_me", instructions="Hi", model="openai:gpt-4o")
    registry.register(expected)
    assert registry.get("get_me") is expected


def test_get_nonexistent_raises(registry):
    with pytest.raises(AgentNotFoundError):
        registry.get("nonexistent")


def test_create_returns_pydantic_agent(registry, tool_registry):
    registry.register(AgentDefinition(
        name="creator_test", instructions="You are a test.", model="test",
    ))
    agent = registry.create("creator_test", tool_registry)
    assert isinstance(agent, Agent)


def test_create_with_tools(registry, tool_registry):
    registry.register(AgentDefinition(
        name="tool_agent", instructions="You use tools.", model="test",
        tools=["dummy_tool"],
    ))
    agent = registry.create("tool_agent", tool_registry)
    assert isinstance(agent, Agent)


def test_create_caches_agent(registry, tool_registry):
    registry.register(AgentDefinition(
        name="cached_test", instructions="test", model="test",
    ))
    a1 = registry.create("cached_test", tool_registry)
    a2 = registry.create("cached_test", tool_registry)
    assert a1 is a2


def test_create_with_output_type(registry, tool_registry):
    from pydantic import BaseModel

    class Output(BaseModel):
        result: str

    registry.register(AgentDefinition(
        name="structured", instructions="output", model="test",
        output_type=Output,
    ))
    agent = registry.create("structured", tool_registry)
    assert isinstance(agent, Agent)
