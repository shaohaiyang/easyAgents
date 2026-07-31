import pytest
from pydantic_ai import ModelResponse, TextPart
from pydantic_ai.models.function import FunctionModel, AgentInfo

from easyagents import (
    AgentDefinition, AgentRegistry, ToolRegistry,
    OrchestratorWorker, SubtaskTemplate,
    HandoffPattern,
    RouterPattern,
)


def make_orchestrator_handler():
    def handler(messages, info: AgentInfo) -> ModelResponse:
        for part in messages[-1].parts:
            content = str(getattr(part, "content", ""))
            if "Research" in content:
                return ModelResponse(parts=[TextPart(content="Found 3 products")])
            if "Analyze" in content:
                return ModelResponse(parts=[TextPart(content="Market growing 20%")])
            if "Synthesize" in content:
                return ModelResponse(parts=[TextPart(content="Combined report ready")])
        return ModelResponse(parts=[TextPart(content="Default")])
    return FunctionModel(handler)


@pytest.mark.asyncio
async def test_orchestrator_end_to_end():
    """Full orchestrator flow: parallel subtasks + synthesis."""
    tools = ToolRegistry()
    agents = AgentRegistry()

    agents.register(AgentDefinition(name="researcher", instructions="Research.", model="test"))
    agents.register(AgentDefinition(name="analyst", instructions="Analyze.", model="test"))
    agents.register(AgentDefinition(name="synthesizer", instructions="Synthesize.", model="test"))

    orch = OrchestratorWorker(
        orchestrator_agent="coordinator",
        subtasks=[
            SubtaskTemplate(agent="researcher", task_template="Research {topic}"),
            SubtaskTemplate(agent="analyst", task_template="Analyze {topic} market"),
        ],
        registry=agents,
        tool_registry=tools,
        synthesis_agent="synthesizer",
    )

    result = await orch.run("调研蓝牙耳机", params={"topic": "bluetooth earphones"}, model=make_orchestrator_handler())

    assert result.output == "Combined report ready"
    assert len(result.subtask_results) == 2
    assert result.usage.requests > 0


@pytest.mark.asyncio
async def test_handoff_end_to_end():
    """Full handoff chain with message history transfer."""
    tools = ToolRegistry()
    agents = AgentRegistry()

    agents.register(AgentDefinition(name="intake", instructions="Intake.", model="test"))
    agents.register(AgentDefinition(name="writer", instructions="Write.", model="test"))

    handoff = HandoffPattern(
        agents=["intake", "writer"],
        registry=agents,
        tool_registry=tools,
        context_mode="full",
    )

    result = await handoff.run("write a report about AI", model=make_orchestrator_handler())

    assert result.agent_chain == ["intake", "writer"]
    assert result.output is not None


@pytest.mark.asyncio
async def test_router_to_orchestrator_composition():
    """Router routes to an orchestrator agent, which runs OrchestratorWorker."""
    tools = ToolRegistry()
    agents = AgentRegistry()

    agents.register(AgentDefinition(
        name="simple_qa", instructions="Answer questions.", model="test",
        description="简单问答",
    ))
    agents.register(AgentDefinition(
        name="research_coordinator", instructions="Coordinate research.", model="test",
        description="协调调研任务",
    ))

    def handler(messages, info: AgentInfo) -> ModelResponse:
        for part in messages[-1].parts:
            content = str(getattr(part, "content", ""))
            if "research" in content.lower() or "调研" in content:
                return ModelResponse(parts=[TextPart(content="research_coordinator")])
        return ModelResponse(parts=[TextPart(content="simple_qa")])

    router = RouterPattern(
        agents=["simple_qa", "research_coordinator"],
        registry=agents,
        tool_registry=tools,
        model="test",
    )

    # Route only (don't execute)
    agent_name = await router.route("帮我调研蓝牙耳机", model=FunctionModel(handler))
    assert agent_name == "research_coordinator"
