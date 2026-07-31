import pytest
from pydantic_ai import ModelResponse, TextPart
from pydantic_ai.models.function import FunctionModel, AgentInfo

from easyagents.core.agent import AgentDefinition, AgentRegistry
from easyagents.core.exceptions import RoutingError
from easyagents.tools.registry import ToolRegistry
from easyagents.patterns.router import RouterPattern


def make_router_handler(routed_name: str = "coder"):
    """Handler that returns an agent name for routing, or executes agent."""
    def handler(messages, info: AgentInfo) -> ModelResponse:
        for part in messages[-1].parts:
            content = str(getattr(part, "content", ""))
            if "debug" in content.lower() or "code" in content.lower():
                return ModelResponse(parts=[TextPart(content="coder")])
            if "research" in content.lower() or "调研" in content:
                return ModelResponse(parts=[TextPart(content="researcher")])
            if "write" in content.lower() or "报告" in content:
                return ModelResponse(parts=[TextPart(content="writer")])
        return ModelResponse(parts=[TextPart(content=routed_name)])
    return FunctionModel(handler)


def make_executor_handler():
    """Handler that simulates agent execution."""
    def handler(messages, info: AgentInfo) -> ModelResponse:
        return ModelResponse(parts=[TextPart(content="Agent executed successfully")])
    return FunctionModel(handler)


@pytest.fixture
def tool_registry():
    return ToolRegistry()


@pytest.fixture
def registry():
    return AgentRegistry()


@pytest.fixture
def setup_agents(registry):
    registry.register(AgentDefinition(
        name="researcher", instructions="Research.", model="test",
        description="调研市场信息",
    ))
    registry.register(AgentDefinition(
        name="coder", instructions="Code.", model="test",
        description="编写和调试代码",
    ))
    registry.register(AgentDefinition(
        name="writer", instructions="Write.", model="test",
        description="撰写文档和报告",
    ))
    return registry


@pytest.mark.asyncio
async def test_router_returns_correct_agent(setup_agents, tool_registry):
    router = RouterPattern(
        agents=["researcher", "coder", "writer"],
        registry=setup_agents,
        tool_registry=tool_registry,
        model="test",
    )

    result = await router.route("help me debug code", model=make_router_handler())
    assert result == "coder"


@pytest.mark.asyncio
async def test_router_run_executes_selected_agent(setup_agents, tool_registry):
    def combined_handler(messages, info):
        for part in messages[-1].parts:
            content = str(getattr(part, "content", ""))
            if "debug" in content.lower():
                return ModelResponse(parts=[TextPart(content="coder")])
        return ModelResponse(parts=[TextPart(content="Agent executed successfully")])

    router = RouterPattern(
        agents=["researcher", "coder", "writer"],
        registry=setup_agents,
        tool_registry=tool_registry,
        model="test",
    )

    result = await router.run("debug my code", model=FunctionModel(combined_handler))
    assert result is not None


@pytest.mark.asyncio
async def test_router_invalid_agent_raises(setup_agents, tool_registry):
    def bad_handler(messages, info):
        return ModelResponse(parts=[TextPart(content="nonexistent_agent")])

    router = RouterPattern(
        agents=["researcher", "coder", "writer"],
        registry=setup_agents,
        tool_registry=tool_registry,
        model="test",
    )

    with pytest.raises(RoutingError):
        await router.route("test", model=FunctionModel(bad_handler))


def test_router_empty_agents_raises(tool_registry, registry):
    with pytest.raises(ValueError):
        RouterPattern(
            agents=[],
            registry=registry,
            tool_registry=tool_registry,
        )


@pytest.mark.asyncio
async def test_router_uses_agent_descriptions(setup_agents, tool_registry):
    """Router should auto-generate prompt from agent descriptions."""
    router = RouterPattern(
        agents=["researcher", "coder", "writer"],
        registry=setup_agents,
        tool_registry=tool_registry,
        model="test",
    )

    prompt = router._build_routing_prompt()
    assert "调研市场信息" in prompt
    assert "编写和调试代码" in prompt
    assert "撰写文档和报告" in prompt
