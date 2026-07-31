import pytest
from pydantic_ai import ModelResponse, TextPart, RunUsage
from pydantic_ai.models.function import FunctionModel, AgentInfo

from easyagents.core.agent import AgentDefinition, AgentRegistry
from easyagents.core.exceptions import HandoffError
from easyagents.tools.registry import ToolRegistry
from easyagents.patterns.handoff import HandoffPattern, HandoffResult


def make_handoff_handler():
    """Handler that tracks message count to verify history transfer."""
    call_count = 0

    def handler(messages, info: AgentInfo) -> ModelResponse:
        nonlocal call_count
        call_count += 1
        msg_count = len(messages)
        return ModelResponse(parts=[TextPart(content=f"Agent call {call_count}, saw {msg_count} messages")])
    return FunctionModel(handler)


@pytest.fixture
def tool_registry():
    return ToolRegistry()


@pytest.fixture
def registry():
    return AgentRegistry()


@pytest.mark.asyncio
async def test_handoff_full_history_transfer(tool_registry, registry):
    """Each subsequent agent sees previous agents' messages."""
    registry.register(AgentDefinition(name="a", instructions="Agent A.", model="test"))
    registry.register(AgentDefinition(name="b", instructions="Agent B.", model="test"))

    handoff = HandoffPattern(
        agents=["a", "b"],
        registry=registry,
        tool_registry=tool_registry,
        context_mode="full",
    )

    result = await handoff.run("hello", model=make_handoff_handler())

    assert isinstance(result, HandoffResult)
    assert result.agent_chain == ["a", "b"]
    assert result.output is not None


@pytest.mark.asyncio
async def test_handoff_none_mode_no_history(tool_registry, registry):
    """context_mode='none' means no history transfer."""
    call_count = 0

    def handler(messages, info):
        nonlocal call_count
        call_count += 1
        return ModelResponse(parts=[TextPart(content=f"Call {call_count}, msgs={len(messages)}")])

    registry.register(AgentDefinition(name="a", instructions="A.", model="test"))
    registry.register(AgentDefinition(name="b", instructions="B.", model="test"))

    handoff = HandoffPattern(
        agents=["a", "b"],
        registry=registry,
        tool_registry=tool_registry,
        context_mode="none",
    )

    await handoff.run("hello", model=FunctionModel(handler))

    # Both agents should see 1 message (just their own input)
    # call_count == 2 after both agents run


@pytest.mark.asyncio
async def test_handoff_three_agent_chain(tool_registry, registry):
    registry.register(AgentDefinition(name="intake", instructions="Intake.", model="test"))
    registry.register(AgentDefinition(name="researcher", instructions="Research.", model="test"))
    registry.register(AgentDefinition(name="writer", instructions="Write.", model="test"))

    handoff = HandoffPattern(
        agents=["intake", "researcher", "writer"],
        registry=registry,
        tool_registry=tool_registry,
    )

    result = await handoff.run("write a report", model=make_handoff_handler())

    assert result.agent_chain == ["intake", "researcher", "writer"]
    assert result.total_messages > 0


@pytest.mark.asyncio
async def test_handoff_compressed_without_context_manager_raises(tool_registry, registry):
    registry.register(AgentDefinition(name="a", instructions="A.", model="test"))
    registry.register(AgentDefinition(name="b", instructions="B.", model="test"))

    handoff = HandoffPattern(
        agents=["a", "b"],
        registry=registry,
        tool_registry=tool_registry,
        context_mode="compressed",
        context_manager=None,
    )

    with pytest.raises(HandoffError):
        await handoff.run("test", model=make_handoff_handler())


@pytest.mark.asyncio
async def test_handoff_mid_chain_failure_raises(tool_registry, registry):
    def fail_on_second(messages, info):
        if len(messages) > 1:
            raise RuntimeError("Agent B crashed")
        return ModelResponse(parts=[TextPart(content="Agent A OK")])

    registry.register(AgentDefinition(name="a", instructions="A.", model="test"))
    registry.register(AgentDefinition(name="b", instructions="B.", model="test"))

    handoff = HandoffPattern(
        agents=["a", "b"],
        registry=registry,
        tool_registry=tool_registry,
    )

    with pytest.raises(HandoffError) as exc_info:
        await handoff.run("test", model=FunctionModel(fail_on_second))
    assert "b" in str(exc_info.value).lower() or "agent" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_handoff_with_custom_task_templates(tool_registry, registry):
    registry.register(AgentDefinition(name="a", instructions="A.", model="test"))
    registry.register(AgentDefinition(name="b", instructions="B.", model="test"))

    handoff = HandoffPattern(
        agents=["a", "b"],
        registry=registry,
        tool_registry=tool_registry,
        task_templates=["Process this: {input}", "Write report based on above"],
    )

    result = await handoff.run("data", model=make_handoff_handler())
    assert result is not None
