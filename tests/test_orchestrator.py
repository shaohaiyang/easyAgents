import asyncio
import pytest
from pydantic_ai import ModelResponse, TextPart, RunUsage
from pydantic_ai.models.function import FunctionModel, AgentInfo

from easyagents.core.agent import AgentDefinition, AgentRegistry
from easyagents.core.exceptions import OrchestrationError
from easyagents.tools.registry import ToolRegistry
from easyagents.patterns.orchestrator import (
    OrchestratorWorker,
    SubtaskTemplate,
    OrchestrationResult,
)


def make_handler():
    """FunctionModel that returns different results based on message content."""
    def handler(messages, info: AgentInfo) -> ModelResponse:
        for part in messages[-1].parts:
            content = str(getattr(part, "content", ""))
            if "Research" in content:
                return ModelResponse(parts=[TextPart(content="Research complete")])
            if "Analyze" in content:
                return ModelResponse(parts=[TextPart(content="Analysis complete")])
            if "Synthesize" in content:
                return ModelResponse(parts=[TextPart(content="Final synthesis")])
        return ModelResponse(parts=[TextPart(content="Default")])
    return FunctionModel(handler)


@pytest.fixture
def tool_registry():
    return ToolRegistry()


@pytest.fixture
def registry():
    return AgentRegistry()


def test_subtask_template_fills_params():
    template = SubtaskTemplate(agent="researcher", task_template="Research {topic}")
    filled = template.task_template.format(topic="bluetooth")
    assert filled == "Research bluetooth"


@pytest.mark.asyncio
async def test_orchestrator_runs_subtasks_in_parallel(tool_registry, registry):
    registry.register(AgentDefinition(name="researcher", instructions="Research.", model="test"))
    registry.register(AgentDefinition(name="analyst", instructions="Analyze.", model="test"))

    orch = OrchestratorWorker(
        orchestrator_agent="coordinator",
        subtasks=[
            SubtaskTemplate(agent="researcher", task_template="Research {topic}"),
            SubtaskTemplate(agent="analyst", task_template="Analyze {topic} market"),
        ],
        registry=registry,
        tool_registry=tool_registry,
    )

    result = await orch.run("test", params={"topic": "bluetooth"}, model=make_handler())

    assert isinstance(result, OrchestrationResult)
    assert len(result.subtask_results) == 2
    assert "Research complete" in str(result.subtask_results[0])
    assert "Analysis complete" in str(result.subtask_results[1])


@pytest.mark.asyncio
async def test_orchestrator_with_synthesis(tool_registry, registry):
    registry.register(AgentDefinition(name="researcher", instructions="Research.", model="test"))
    registry.register(AgentDefinition(name="analyst", instructions="Analyze.", model="test"))
    registry.register(AgentDefinition(name="synthesizer", instructions="Synthesize.", model="test"))

    orch = OrchestratorWorker(
        orchestrator_agent="coordinator",
        subtasks=[
            SubtaskTemplate(agent="researcher", task_template="Research {topic}"),
            SubtaskTemplate(agent="analyst", task_template="Analyze {topic}"),
        ],
        registry=registry,
        tool_registry=tool_registry,
        synthesis_agent="synthesizer",
    )

    result = await orch.run("test", params={"topic": "bluetooth"}, model=make_handler())

    assert result.output == "Final synthesis"


@pytest.mark.asyncio
async def test_orchestrator_partial_failure_degrades(tool_registry, registry):
    """One subtask fails, other succeeds, result has None for failed."""
    def failing_handler(messages, info):
        for part in messages[-1].parts:
            content = str(getattr(part, "content", ""))
            if "Research" in content:
                return ModelResponse(parts=[TextPart(content="Research OK")])
        raise RuntimeError("Analyst failed")

    registry.register(AgentDefinition(name="researcher", instructions="Research.", model="test"))
    registry.register(AgentDefinition(name="analyst", instructions="Analyze.", model="test"))

    orch = OrchestratorWorker(
        orchestrator_agent="coordinator",
        subtasks=[
            SubtaskTemplate(agent="researcher", task_template="Research {topic}"),
            SubtaskTemplate(agent="analyst", task_template="Analyze {topic}"),
        ],
        registry=registry,
        tool_registry=tool_registry,
    )

    result = await orch.run("test", params={"topic": "x"}, model=FunctionModel(failing_handler))

    assert None in result.subtask_results
    assert "Research OK" in str(result.subtask_results[0])


@pytest.mark.asyncio
async def test_orchestrator_all_fail_raises_error(tool_registry, registry):
    def always_fail(messages, info):
        raise RuntimeError("All failed")

    registry.register(AgentDefinition(name="a", instructions="A.", model="test"))
    registry.register(AgentDefinition(name="b", instructions="B.", model="test"))

    orch = OrchestratorWorker(
        orchestrator_agent="coordinator",
        subtasks=[
            SubtaskTemplate(agent="a", task_template="Do {x}"),
            SubtaskTemplate(agent="b", task_template="Do {x}"),
        ],
        registry=registry,
        tool_registry=tool_registry,
    )

    with pytest.raises(OrchestrationError):
        await orch.run("test", params={"x": "something"}, model=FunctionModel(always_fail))


@pytest.mark.asyncio
async def test_orchestrator_parallelism(tool_registry, registry):
    """Verify subtasks run in parallel (total time < sum of individual times)."""
    import time

    def slow_handler(messages, info):
        time.sleep(0.3)
        return ModelResponse(parts=[TextPart(content="Done")])

    registry.register(AgentDefinition(name="a", instructions="A.", model="test"))
    registry.register(AgentDefinition(name="b", instructions="B.", model="test"))

    orch = OrchestratorWorker(
        orchestrator_agent="coordinator",
        subtasks=[
            SubtaskTemplate(agent="a", task_template="Do {x}"),
            SubtaskTemplate(agent="b", task_template="Do {x}"),
        ],
        registry=registry,
        tool_registry=tool_registry,
    )

    start = time.time()
    await orch.run("test", params={"x": "task"}, model=FunctionModel(slow_handler))
    elapsed = time.time() - start

    # If parallel, elapsed < 0.6s (2 * 0.3s). Allow margin.
    assert elapsed < 0.55, f"Expected parallel (<0.55s), got {elapsed:.2f}s"


@pytest.mark.asyncio
async def test_orchestrator_synthesis_failure_falls_back(tool_registry, registry):
    """If synthesis agent fails, output falls back to joined subtask results."""
    def handler(messages, info):
        for part in messages[-1].parts:
            content = str(getattr(part, "content", ""))
            if "Research" in content:
                return ModelResponse(parts=[TextPart(content="Research OK")])
            if "Analyze" in content:
                return ModelResponse(parts=[TextPart(content="Analysis OK")])
            if "Synthesize" in content:
                raise RuntimeError("Synthesis failed")
        return ModelResponse(parts=[TextPart(content="Default")])

    registry.register(AgentDefinition(name="researcher", instructions="Research.", model="test"))
    registry.register(AgentDefinition(name="analyst", instructions="Analyze.", model="test"))
    registry.register(AgentDefinition(name="synthesizer", instructions="Synthesize.", model="test"))

    orch = OrchestratorWorker(
        orchestrator_agent="coordinator",
        subtasks=[
            SubtaskTemplate(agent="researcher", task_template="Research {topic}"),
            SubtaskTemplate(agent="analyst", task_template="Analyze {topic}"),
        ],
        registry=registry,
        tool_registry=tool_registry,
        synthesis_agent="synthesizer",
    )

    result = await orch.run("test", params={"topic": "x"}, model=FunctionModel(handler))

    # Should fall back to joined results
    assert "Research OK" in str(result.output)
    assert "Analysis OK" in str(result.output)

