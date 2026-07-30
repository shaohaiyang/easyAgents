import pytest
from pydantic_ai import RunUsage, ModelResponse, TextPart
from pydantic_ai.models.function import FunctionModel, AgentInfo

from easyagents.core.agent import AgentDefinition, AgentRegistry
from easyagents.core.exceptions import DelegationError
from easyagents.tools.registry import ToolRegistry
from easyagents.patterns.delegation import DelegationManager


@pytest.fixture
def tool_registry():
    tr = ToolRegistry()
    tr.register("web_search", lambda q: [{"title": "R", "url": "https://x.com", "snippet": "..."}])
    return tr


@pytest.fixture
def registry():
    return AgentRegistry()


def make_handler(output: str = "Done"):
    def handler(messages: list, info: AgentInfo) -> ModelResponse:
        return ModelResponse(parts=[TextPart(content=output)])
    return FunctionModel(handler)


def test_delegation_tool_names_use_delegate_prefix(tool_registry, registry):
    registry.register(AgentDefinition(name="researcher", instructions="Research.", model="openai:gpt-4o"))
    dm = DelegationManager("parent", ["researcher"], registry, tool_registry)
    tools = dm.create_delegation_tools()
    assert len(tools) == 1
    assert tools[0].name == "delegate_researcher"


def test_delegation_tool_count_matches_subagents(tool_registry, registry):
    for name in ["a", "b", "c"]:
        registry.register(AgentDefinition(name=name, instructions=f"I'm {name}", model="openai:gpt-4o"))
    dm = DelegationManager("parent", ["a", "b", "c"], registry, tool_registry)
    tools = dm.create_delegation_tools()
    assert len(tools) == 3


@pytest.mark.asyncio
async def test_delegate_runs_subagent_and_returns_output(tool_registry, registry):
    registry.register(AgentDefinition(
        name="researcher", instructions="You research.", model="test",
    ))
    dm = DelegationManager("parent", ["researcher"], registry, tool_registry)
    usage = RunUsage()
    result = await dm.delegate(
        "researcher", "test task", usage,
        model=make_handler("Found: AirPods Pro 2"),
    )
    assert result == "Found: AirPods Pro 2"


@pytest.mark.asyncio
async def test_delegate_passes_usage(tool_registry, registry):
    registry.register(AgentDefinition(
        name="counter", instructions="You count.", model="test",
    ))
    dm = DelegationManager("parent", ["counter"], registry, tool_registry)
    usage = RunUsage()
    await dm.delegate("counter", "count to 3", usage, model=make_handler("Done"))
    assert usage.requests > 0


@pytest.mark.asyncio
async def test_delegate_nonexistent_subagent_raises(tool_registry, registry):
    dm = DelegationManager("parent", ["ghost"], registry, tool_registry)
    usage = RunUsage()
    with pytest.raises(DelegationError):
        await dm.delegate("ghost", "task", usage, model=make_handler())


def test_agent_registry_create_injects_delegation_tools(tool_registry, registry):
    registry.register(AgentDefinition(name="helper", instructions="Help.", model="test"))
    registry.register(AgentDefinition(
        name="boss", instructions="You delegate.", model="test",
        subagents=["helper"],
    ))
    agent = registry.create("boss", tool_registry)
    assert agent is not None
    result = agent.run_sync("do it", model=make_handler("OK"))
    assert result.output is not None


@pytest.mark.asyncio
async def test_delegation_tool_nonexistent_subagent_raises_error(tool_registry, registry):
    from pydantic_ai import ToolCallPart

    registry.register(AgentDefinition(
        name="parent", instructions="Delegate.", model="test",
        subagents=["ghost"],
    ))

    calls = 0

    def handler(messages, info):
        nonlocal calls
        calls += 1
        return ModelResponse(
            parts=[ToolCallPart(tool_name="delegate_ghost", args={"task": "do it"})]
        )

    agent = registry.create("parent", tool_registry)
    with pytest.raises(DelegationError):
        await agent.run("start", model=FunctionModel(handler))


@pytest.mark.asyncio
async def test_delegation_tool_executed_through_agent_run(tool_registry, registry):
    from pydantic_ai import ToolCallPart

    registry.register(AgentDefinition(
        name="child", instructions="You help.", model="test",
    ))
    registry.register(AgentDefinition(
        name="parent", instructions="Delegate to child when needed.", model="test",
        subagents=["child"],
    ))

    calls = 0

    def handler(messages, info):
        nonlocal calls
        calls += 1
        if calls == 1:
            return ModelResponse(
                parts=[ToolCallPart(tool_name="delegate_child", args={"task": "help me"})]
            )
        return ModelResponse(parts=[TextPart(content="Child result received")])

    agent = registry.create("parent", tool_registry)
    result = await agent.run("do something", model=FunctionModel(handler))
    assert calls >= 2, f"Expected >=2 model calls, got {calls}"
    assert result.output is not None
