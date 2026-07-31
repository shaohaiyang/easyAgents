# EasyAgents Phase 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add three multi-agent orchestration patterns: OrchestratorWorker (parallel subtasks), HandoffPattern (sequential agent switching), and RouterPattern (LLM intent routing).

**Architecture:** Three independent pattern classes in `patterns/`, each accepting AgentRegistry + ToolRegistry. No changes to AgentDefinition. All patterns accept `model` override for testability.

**Tech Stack:** Python 3.11+, Pydantic AI, asyncio (asyncio.gather), pytest/pytest-asyncio

## Global Constraints

- Python >= 3.11
- pydantic-ai >= 0.0.30, pydantic >= 2.0
- Source layout: `src/easyagents/`
- Tests in `tests/` directory
- No real LLM API calls in tests - use `TestModel` or `FunctionModel`
- Use `.venv/bin/python` to run Python and `.venv/bin/python -m pytest` to run tests
- Backward compatible: existing 63 tests must still pass
- No new dependencies

---

### Task 1: Exceptions

**Files:**
- Modify: `src/easyagents/core/exceptions.py`

**Interfaces:**
- Consumes: nothing
- Produces: `OrchestrationError`, `HandoffError`, `RoutingError`

- [ ] **Step 1: Add new exceptions**

Append to `src/easyagents/core/exceptions.py`:

```python
class OrchestrationError(EasyAgentsError):
    """Raised when orchestrator-worker execution fails."""


class HandoffError(EasyAgentsError):
    """Raised when a handoff between agents fails."""


class RoutingError(EasyAgentsError):
    """Raised when agent routing fails (no match, LLM error)."""
```

- [ ] **Step 2: Verify import**

```bash
.venv/bin/python -c "from easyagents.core.exceptions import OrchestrationError, HandoffError, RoutingError; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Run existing tests to verify no regression**

```bash
.venv/bin/python -m pytest tests/ -v
```

Expected: 63 passed

- [ ] **Step 4: Commit**

```bash
git add src/easyagents/core/exceptions.py
git commit -m "feat: add Phase 2 exceptions - OrchestrationError, HandoffError, RoutingError"
```

---

### Task 2: OrchestratorWorker

**Files:**
- Create: `src/easyagents/patterns/orchestrator.py`
- Create: `tests/test_orchestrator.py`

**Interfaces:**
- Consumes: `AgentRegistry` from `easyagents.core.agent`, `ToolRegistry` from `easyagents.tools.registry`, `RunUsage` from `pydantic_ai`, `OrchestrationError` from `easyagents.core.exceptions`
- Produces: `SubtaskTemplate`, `OrchestrationResult`, `OrchestratorWorker`

- [ ] **Step 1: Write the failing test for OrchestratorWorker**

File `tests/test_orchestrator.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
.venv/bin/python -m pytest tests/test_orchestrator.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'easyagents.patterns.orchestrator'`

- [ ] **Step 3: Write patterns/orchestrator.py**

```python
import asyncio
from dataclasses import dataclass, field
from typing import Any

from pydantic_ai import RunUsage

from easyagents.core.exceptions import OrchestrationError


@dataclass
class SubtaskTemplate:
    """A predefined subtask for parallel execution."""
    agent: str
    task_template: str
    description: str = ""


@dataclass
class OrchestrationResult:
    """Result of orchestrator-worker execution."""
    output: Any
    subtask_results: list[Any]
    usage: RunUsage


class OrchestratorWorker:
    """Executes predefined subtask templates in parallel across multiple subagents."""

    def __init__(
        self,
        orchestrator_agent: str,
        subtasks: list[SubtaskTemplate],
        registry: Any,
        tool_registry: Any,
        synthesis_agent: str | None = None,
        context_manager: Any = None,
    ) -> None:
        self.orchestrator_agent = orchestrator_agent
        self.subtasks = subtasks
        self.registry = registry
        self.tool_registry = tool_registry
        self.synthesis_agent = synthesis_agent
        self.context_manager = context_manager

    async def run(
        self,
        user_input: str,
        params: dict[str, str] | None = None,
        model: Any = None,
    ) -> OrchestrationResult:
        params = params or {}

        filled_tasks = []
        for subtask in self.subtasks:
            try:
                task = subtask.task_template.format(**params)
            except KeyError as e:
                raise OrchestrationError(
                    f"Missing parameter {e} for subtask '{subtask.agent}'"
                ) from e
            filled_tasks.append((subtask.agent, task))

        usage = RunUsage()

        results = await asyncio.gather(
            *[self._run_subtask(name, task, usage, model) for name, task in filled_tasks],
            return_exceptions=True,
        )

        subtask_results: list[Any] = []
        failures: list[str] = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                subtask_results.append(None)
                failures.append(f"{filled_tasks[i][0]}: {result}")
            else:
                subtask_results.append(result)

        if all(r is None for r in subtask_results):
            raise OrchestrationError(
                f"All subtasks failed: {'; '.join(failures)}"
            )

        if self.synthesis_agent:
            valid_results = [str(r) for r in subtask_results if r is not None]
            synthesis_input = "\n".join(valid_results)
            try:
                agent = self.registry.create(self.synthesis_agent, self.tool_registry)
                run_kwargs: dict[str, Any] = {"usage": usage}
                if model is not None:
                    run_kwargs["model"] = model
                result = await agent.run(
                    f"Synthesize the following results:\n{synthesis_input}",
                    **run_kwargs,
                )
                output = result.output
            except Exception:
                output = "\n".join(str(r) for r in subtask_results if r is not None)
        else:
            output = "\n".join(str(r) for r in subtask_results if r is not None)

        return OrchestrationResult(
            output=output,
            subtask_results=subtask_results,
            usage=usage,
        )

    async def _run_subtask(
        self,
        agent_name: str,
        task: str,
        usage: RunUsage,
        model: Any = None,
    ) -> Any:
        agent = self.registry.create(agent_name, self.tool_registry)
        run_kwargs: dict[str, Any] = {"usage": usage}
        if model is not None:
            run_kwargs["model"] = model
        result = await agent.run(task, **run_kwargs)
        return result.output
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/bin/python -m pytest tests/test_orchestrator.py -v
```

Expected: 6 passed

- [ ] **Step 5: Run all tests to verify no regression**

```bash
.venv/bin/python -m pytest tests/ -v
```

Expected: 69 passed (63 existing + 6 new)

- [ ] **Step 6: Commit**

```bash
git add src/easyagents/patterns/orchestrator.py tests/test_orchestrator.py
git commit -m "feat: OrchestratorWorker with parallel subtask execution and synthesis"
```

---

### Task 3: HandoffPattern

**Files:**
- Create: `src/easyagents/patterns/handoff.py`
- Create: `tests/test_handoff.py`

**Interfaces:**
- Consumes: `AgentRegistry`, `ToolRegistry`, `RunUsage`, `HandoffError`, `ContextManager` (optional)
- Produces: `HandoffResult`, `HandoffPattern`

- [ ] **Step 1: Write the failing test for HandoffPattern**

File `tests/test_handoff.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
.venv/bin/python -m pytest tests/test_handoff.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'easyagents.patterns.handoff'`

- [ ] **Step 3: Write patterns/handoff.py**

```python
from dataclasses import dataclass
from typing import Any

from pydantic_ai import RunUsage

from easyagents.core.exceptions import HandoffError


@dataclass
class HandoffResult:
    """Result of handoff chain execution."""
    output: Any
    agent_chain: list[str]
    total_messages: int
    usage: RunUsage


class HandoffPattern:
    """Executes a chain of agents sequentially, transferring conversation history."""

    def __init__(
        self,
        agents: list[str],
        registry: Any,
        tool_registry: Any,
        context_mode: str = "full",
        context_manager: Any = None,
        task_templates: list[str] | None = None,
    ) -> None:
        if not agents:
            raise ValueError("agents list cannot be empty")
        if task_templates is not None and len(task_templates) != len(agents):
            raise ValueError(
                f"task_templates length ({len(task_templates)}) must match agents length ({len(agents)})"
            )

        self.agents = agents
        self.registry = registry
        self.tool_registry = tool_registry
        self.context_mode = context_mode
        self.context_manager = context_manager
        self.task_templates = task_templates

    async def run(
        self,
        user_input: str,
        model: Any = None,
    ) -> HandoffResult:
        usage = RunUsage()
        history: list = []
        total_messages = 0
        output: Any = None

        for i, agent_name in enumerate(self.agents):
            if i == 0:
                task = user_input
                if self.task_templates:
                    task = self.task_templates[0].format(input=user_input)
                run_kwargs: dict[str, Any] = {"usage": usage}
                if model is not None:
                    run_kwargs["model"] = model
                if history:
                    run_kwargs["message_history"] = history
                result = await self._run_agent(agent_name, task, **run_kwargs)
            else:
                task = (
                    self.task_templates[i]
                    if self.task_templates
                    else "Continue based on the previous conversation."
                )
                run_kwargs = {"usage": usage}
                if model is not None:
                    run_kwargs["model"] = model
                if history:
                    run_kwargs["message_history"] = history
                result = await self._run_agent(agent_name, task, **run_kwargs)

            output = result.output
            messages = result.all_messages()
            total_messages += len(messages)

            history = await self._process_context(messages, model)

        return HandoffResult(
            output=output,
            agent_chain=list(self.agents),
            total_messages=total_messages,
            usage=usage,
        )

    async def _run_agent(self, agent_name: str, task: str, **kwargs) -> Any:
        try:
            agent = self.registry.create(agent_name, self.tool_registry)
            result = await agent.run(task, **kwargs)
            return result
        except Exception as e:
            raise HandoffError(
                f"Agent '{agent_name}' failed during handoff: {e}"
            ) from e

    async def _process_context(self, messages: list, model: Any = None) -> list:
        if self.context_mode == "none":
            return []
        if self.context_mode == "compressed":
            if self.context_manager is None:
                raise HandoffError(
                    "context_mode='compressed' requires a context_manager"
                )
            return await self.context_manager.compress_if_needed(messages, model=model)
        return messages
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/bin/python -m pytest tests/test_handoff.py -v
```

Expected: 6 passed

- [ ] **Step 5: Run all tests to verify no regression**

```bash
.venv/bin/python -m pytest tests/ -v
```

Expected: 75 passed (69 existing + 6 new)

- [ ] **Step 6: Commit**

```bash
git add src/easyagents/patterns/handoff.py tests/test_handoff.py
git commit -m "feat: HandoffPattern with configurable context transfer between agents"
```

---

### Task 4: RouterPattern

**Files:**
- Create: `src/easyagents/patterns/router.py`
- Create: `tests/test_router.py`

**Interfaces:**
- Consumes: `AgentRegistry`, `ToolRegistry`, `RoutingError`
- Produces: `RouterPattern`

- [ ] **Step 1: Write the failing test for RouterPattern**

File `tests/test_router.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
.venv/bin/python -m pytest tests/test_router.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'easyagents.patterns.router'`

- [ ] **Step 3: Write patterns/router.py**

```python
from typing import Any

from pydantic_ai import Agent

from easyagents.core.exceptions import RoutingError


class RouterPattern:
    """Routes user input to the best agent using LLM intent classification."""

    def __init__(
        self,
        agents: list[str],
        registry: Any,
        tool_registry: Any,
        model: str = "openai:gpt-4o",
        routing_prompt: str = "",
    ) -> None:
        if not agents:
            raise ValueError("agents list cannot be empty")

        self.agents = agents
        self.registry = registry
        self.tool_registry = tool_registry
        self.model = model
        self.routing_prompt = routing_prompt

    async def route(
        self,
        user_input: str,
        model: Any = None,
    ) -> str:
        """Analyze user input and return the best agent name."""
        system_prompt = self.routing_prompt or self._build_routing_prompt()

        router_agent = Agent(model=self.model, system_prompt=system_prompt)

        run_kwargs: dict[str, Any] = {}
        if model is not None:
            run_kwargs["model"] = model

        result = await router_agent.run(user_input, **run_kwargs)
        agent_name = str(result.output).strip()

        if agent_name not in self.agents:
            raise RoutingError(
                f"Router returned unknown agent '{agent_name}'. "
                f"Valid agents: {self.agents}"
            )

        return agent_name

    async def run(
        self,
        user_input: str,
        model: Any = None,
    ) -> Any:
        """Route + execute: route first, then run the selected agent."""
        agent_name = await self.route(user_input, model=model)

        agent = self.registry.create(agent_name, self.tool_registry)
        run_kwargs: dict[str, Any] = {}
        if model is not None:
            run_kwargs["model"] = model
        result = await agent.run(user_input, **run_kwargs)
        return result.output

    def _build_routing_prompt(self) -> str:
        """Auto-generate routing prompt from agent descriptions."""
        lines = [
            "You are a router. Given the user input, select the best agent.",
            "Available agents:",
        ]
        for name in self.agents:
            try:
                definition = self.registry.get(name)
                desc = definition.description or name
            except Exception:
                desc = name
            lines.append(f"- {name}: {desc}")
        lines.append("Respond with ONLY the agent name, nothing else.")
        return "\n".join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/bin/python -m pytest tests/test_router.py -v
```

Expected: 5 passed

- [ ] **Step 5: Run all tests to verify no regression**

```bash
.venv/bin/python -m pytest tests/ -v
```

Expected: 80 passed (75 existing + 5 new)

- [ ] **Step 6: Commit**

```bash
git add src/easyagents/patterns/router.py tests/test_router.py
git commit -m "feat: RouterPattern with LLM intent classification for agent routing"
```

---

### Task 5: Public API Wiring + Integration Tests

**Files:**
- Modify: `src/easyagents/__init__.py`
- Create: `tests/test_phase2_integration.py`

**Interfaces:**
- Consumes: All Phase 2 modules
- Produces: Updated public API with 29 symbols; integration tests

- [ ] **Step 1: Update __init__.py with new exports**

Add these imports to `src/easyagents/__init__.py` (after existing pattern/tools imports):

```python
from easyagents.patterns.orchestrator import OrchestratorWorker, SubtaskTemplate, OrchestrationResult
from easyagents.patterns.handoff import HandoffPattern, HandoffResult
from easyagents.patterns.router import RouterPattern
```

Add these to the existing exceptions import:

```python
from easyagents.core.exceptions import (
    # ... existing ...
    OrchestrationError,
    HandoffError,
    RoutingError,
)
```

Add to `__all__`:

```python
    # Phase 2 (new)
    "OrchestratorWorker",
    "SubtaskTemplate",
    "OrchestrationResult",
    "HandoffPattern",
    "HandoffResult",
    "RouterPattern",
    "OrchestrationError",
    "HandoffError",
    "RoutingError",
```

- [ ] **Step 2: Verify all symbols importable**

```bash
.venv/bin/python -c "
from easyagents import (
    OrchestratorWorker, SubtaskTemplate, OrchestrationResult,
    HandoffPattern, HandoffResult, RouterPattern,
    OrchestrationError, HandoffError, RoutingError,
)
print('All Phase 2 symbols OK')
"
```

Expected: `All Phase 2 symbols OK`

- [ ] **Step 3: Write integration tests**

File `tests/test_phase2_integration.py`:

```python
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
```

- [ ] **Step 4: Run all tests**

```bash
.venv/bin/python -m pytest tests/ -v
```

Expected: 83 passed (80 existing + 3 new)

- [ ] **Step 5: Run demo script to verify no breakage**

```bash
.venv/bin/python scripts/demo.py
```

Expected: `Done!` output

- [ ] **Step 6: Commit**

```bash
git add src/easyagents/__init__.py tests/test_phase2_integration.py
git commit -m "feat: wire Phase 2 public API and add integration tests"
```
