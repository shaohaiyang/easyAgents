import json
import pytest
from pydantic_ai import ModelResponse, TextPart
from pydantic_ai.models.function import FunctionModel, AgentInfo

from easyagents.core.agent import AgentDefinition, AgentRegistry
from easyagents.core.exceptions import OrchestrationError
from easyagents.tools.registry import ToolRegistry
from easyagents.patterns.orchestrator import DynamicOrchestrator, DynamicSubtask


def make_decompose_handler(subtasks_json: str):
    """Handler that returns JSON subtask list for decomposition queries."""
    def handler(messages, info: AgentInfo) -> ModelResponse:
        content = ""
        for part in messages[-1].parts:
            content += str(getattr(part, "content", ""))
        if "decomposer" in content.lower() or "Break" in content or "break" in content:
            return ModelResponse(parts=[TextPart(content=subtasks_json)])
        return ModelResponse(parts=[TextPart(content="Agent executed")])
    return FunctionModel(handler)


@pytest.fixture
def tool_registry():
    return ToolRegistry()


@pytest.fixture
def registry():
    r = AgentRegistry()
    r.register(AgentDefinition(name="researcher", instructions="Research.", model="test", description="调研市场"))
    r.register(AgentDefinition(name="writer", instructions="Write.", model="test", description="撰写报告"))
    return r


@pytest.mark.asyncio
async def test_decompose_returns_subtasks(registry, tool_registry):
    subtasks_json = json.dumps([
        {"agent": "researcher", "task": "Search for data", "rationale": "Need data"},
        {"agent": "writer", "task": "Write report", "rationale": "Need report"},
    ])

    dyn = DynamicOrchestrator(
        agents=["researcher", "writer"],
        registry=registry,
        tool_registry=tool_registry,
        model="test",
    )

    subtasks = await dyn.decompose("调研并写报告", model=make_decompose_handler(subtasks_json))

    assert len(subtasks) == 2
    assert isinstance(subtasks[0], DynamicSubtask)
    assert subtasks[0].agent == "researcher"
    assert subtasks[0].task == "Search for data"


@pytest.mark.asyncio
async def test_run_executes_subtasks(registry, tool_registry):
    subtasks_json = json.dumps([
        {"agent": "researcher", "task": "Search", "rationale": "Need data"},
        {"agent": "writer", "task": "Write", "rationale": "Need report"},
    ])

    dyn = DynamicOrchestrator(
        agents=["researcher", "writer"],
        registry=registry,
        tool_registry=tool_registry,
        model="test",
    )

    result = await dyn.run("调研并写报告", model=make_decompose_handler(subtasks_json))

    assert result is not None
    assert len(result.subtask_results) == 2


@pytest.mark.asyncio
async def test_decompose_invalid_json_raises(registry, tool_registry):
    def handler(messages, info):
        return ModelResponse(parts=[TextPart(content="not valid json")])

    dyn = DynamicOrchestrator(
        agents=["researcher", "writer"],
        registry=registry,
        tool_registry=tool_registry,
        model="test",
    )

    with pytest.raises(OrchestrationError):
        await dyn.decompose("task", model=FunctionModel(handler))


@pytest.mark.asyncio
async def test_decompose_unknown_agent_raises(registry, tool_registry):
    subtasks_json = json.dumps([
        {"agent": "nonexistent", "task": "Do something", "rationale": "Why"},
    ])

    dyn = DynamicOrchestrator(
        agents=["researcher", "writer"],
        registry=registry,
        tool_registry=tool_registry,
        model="test",
    )

    with pytest.raises(OrchestrationError):
        await dyn.decompose("task", model=make_decompose_handler(subtasks_json))


@pytest.mark.asyncio
async def test_run_sequential(registry, tool_registry):
    subtasks_json = json.dumps([
        {"agent": "researcher", "task": "Search", "rationale": "Need data"},
        {"agent": "writer", "task": "Write", "rationale": "Need report"},
    ])

    dyn = DynamicOrchestrator(
        agents=["researcher", "writer"],
        registry=registry,
        tool_registry=tool_registry,
        model="test",
    )

    result = await dyn.run_sequential("调研并写报告", model=make_decompose_handler(subtasks_json))

    assert result is not None
    assert len(result.subtask_results) == 2
