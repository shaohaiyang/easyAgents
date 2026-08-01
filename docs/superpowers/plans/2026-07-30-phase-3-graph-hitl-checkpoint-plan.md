# EasyAgents Phase 3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Add graph state machine with HITL, checkpoint/rollback, and dynamic task decomposition.

**Architecture:** Uses pydantic_graph's `BaseNode`/`GraphRunContext`/`End` with a custom graph runner in `GraphWorkflow`. HITL via return-and-resume pattern. Checkpoints stored via SessionStore. DynamicOrchestrator uses LLM for task decomposition.

**Tech Stack:** Python 3.11+, pydantic_graph (BaseNode, GraphRunContext, End), pydantic, asyncio

## Global Constraints

- Python >= 3.11, pydantic-ai >= 0.0.30
- Source layout: `src/easyagents/`
- No real LLM API calls in tests - use FunctionModel/TestModel
- Use `.venv/bin/python` and `.venv/bin/python -m pytest`
- Backward compatible: existing 85 tests must pass
- No new dependencies
- `End` constructor takes positional `data` arg: `End('result')`, NOT `End(result='result')`

---

### Task 1: Exceptions

**Files:**
- Modify: `src/easyagents/core/exceptions.py`

- [ ] **Step 1: Add exceptions**

```python
class WorkflowError(EasyAgentsError):
    """Raised when a graph workflow execution fails."""


class CheckpointError(EasyAgentsError):
    """Raised when checkpoint save/load/rollback fails."""


class ApprovalError(EasyAgentsError):
    """Raised when approval resumption fails (invalid state, already resumed)."""
```

- [ ] **Step 2: Verify**

```bash
.venv/bin/python -c "from easyagents.core.exceptions import WorkflowError, CheckpointError, ApprovalError; print('OK')"
.venv/bin/python -m pytest tests/ -v
```

Expected: `OK`, 85 passed

- [ ] **Step 3: Commit**

```bash
git add src/easyagents/core/exceptions.py
git commit -m "feat: add Phase 3 exceptions - WorkflowError, CheckpointError, ApprovalError"
```

---

### Task 2: Graph Nodes + GraphWorkflow + HITL

**Files:**
- Create: `src/easyagents/workflows/__init__.py`
- Create: `src/easyagents/workflows/nodes.py`
- Create: `src/easyagents/workflows/graph.py`
- Create: `tests/test_graph_workflow.py`

**Interfaces:**
- Consumes: `AgentRegistry`, `ToolRegistry`, `BaseNode`/`GraphRunContext`/`End` from pydantic_graph
- Produces: `AgentNode`, `ApprovalNode`, `GraphWorkflow`, `GraphResult`, `PendingApproval`, `ApprovalResult`

- [ ] **Step 1: Write the failing test**

File `tests/test_graph_workflow.py`:

```python
import pytest
from pydantic import BaseModel
from pydantic_ai import ModelResponse, TextPart, RunUsage
from pydantic_ai.models.function import FunctionModel, AgentInfo
from pydantic_graph import BaseNode, GraphRunContext, End

from easyagents.core.agent import AgentDefinition, AgentRegistry
from easyagents.tools.registry import ToolRegistry
from easyagents.workflows.nodes import AgentNode, ApprovalNode
from easyagents.workflows.graph import (
    GraphWorkflow, GraphResult, PendingApproval, ApprovalResult,
)


class TestState(BaseModel):
    query: str = ""
    results: list[str] = []
    usage: RunUsage = None

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if self.usage is None:
            self.usage = RunUsage()


def make_handler(output: str = "Agent result"):
    def handler(messages, info: AgentInfo) -> ModelResponse:
        return ModelResponse(parts=[TextPart(content=output)])
    return FunctionModel(handler)


@pytest.fixture
def tool_registry():
    return ToolRegistry()


@pytest.fixture
def registry():
    return AgentRegistry()


@pytest.mark.asyncio
async def test_agent_node_executes_agent(registry, tool_registry):
    """AgentNode runs a registered agent and stores output in state."""
    registry.register(AgentDefinition(
        name="worker", instructions="Work.", model="test",
    ))

    class MyState(TestState):
        pass

    class MyNode(AgentNode[MyState]):
        agent_name: str = "worker"
        task: str = "do work"
        next_node: End = None

        async def run(self, ctx: GraphRunContext[MyState]) -> End:
            agent = registry.create("worker", tool_registry)
            result = await agent.run("do work", model=make_handler("Done"))
            ctx.state.results.append(result.output)
            return End("completed")

    wf = GraphWorkflow(registry=registry, tool_registry=tool_registry)
    result = await wf.run(MyNode(), MyState(query="test"), model=make_handler("Done"))

    assert isinstance(result, GraphResult)
    assert result.output == "completed"


@pytest.mark.asyncio
async def test_graph_pauses_at_approval_node(registry, tool_registry):
    """ApprovalNode causes GraphWorkflow to return PendingApproval."""
    registry.register(AgentDefinition(name="worker", instructions="Work.", model="test"))

    class MyState(TestState):
        pass

    class WorkNode(AgentNode[MyState]):
        agent_name: str = "worker"
        task: str = "work"

        async def run(self, ctx: GraphRunContext[MyState]) -> "ApprovalNode[MyState]":
            agent = registry.create("worker", tool_registry)
            result = await agent.run("work", model=make_handler("Work done"))
            ctx.state.results.append(result.output)
            return ApprovalNode(prompt="Approve?", next_node=End("final"))

    class ApprovalNode(BaseNode[MyState]):
        prompt: str
        next_node: BaseNode[MyState]

        async def run(self, ctx: GraphRunContext[MyState]) -> End:
            return End(PendingApproval(
                prompt=self.prompt,
                state=ctx.state,
                resume_node=self.next_node,
            ))

    wf = GraphWorkflow(registry=registry, tool_registry=tool_registry)
    result = await wf.run(WorkNode(), MyState(query="test"), model=make_handler("Work done"))

    assert isinstance(result, PendingApproval)
    assert result.prompt == "Approve?"


@pytest.mark.asyncio
async def test_resume_after_approval(registry, tool_registry):
    """resume() continues execution after approval."""
    registry.register(AgentDefinition(name="worker", instructions="Work.", model="test"))

    class MyState(TestState):
        pass

    class FinalNode(BaseNode[MyState]):
        async def run(self, ctx: GraphRunContext[MyState]) -> End:
            return End("final output")

    pending = PendingApproval(
        prompt="Approve?",
        state=MyState(query="test", results=["interim"]),
        resume_node=FinalNode(),
    )

    wf = GraphWorkflow(registry=registry, tool_registry=tool_registry)
    result = await wf.resume(pending, ApprovalResult(approved=True), model=make_handler())

    assert isinstance(result, GraphResult)
    assert result.output == "final output"


@pytest.mark.asyncio
async def test_resume_rejected_returns_feedback(registry, tool_registry):
    """resume() with rejected approval returns feedback as output."""
    class MyState(TestState):
        pass

    class FinalNode(BaseNode[MyState]):
        async def run(self, ctx: GraphRunContext[MyState]) -> End:
            return End("should not reach")

    pending = PendingApproval(
        prompt="Approve?",
        state=MyState(query="test"),
        resume_node=FinalNode(),
    )

    wf = GraphWorkflow(registry=registry, tool_registry=tool_registry)
    result = await wf.resume(pending, ApprovalResult(approved=False, feedback="Needs revision"))

    assert isinstance(result, GraphResult)
    assert "Needs revision" in str(result.output)


@pytest.mark.asyncio
async def test_multi_node_graph(registry, tool_registry):
    """Graph with multiple agent nodes executes in sequence."""
    registry.register(AgentDefinition(name="a", instructions="A.", model="test"))
    registry.register(AgentDefinition(name="b", instructions="B.", model="test"))

    class MyState(TestState):
        pass

    class NodeB(AgentNode[MyState]):
        agent_name: str = "b"
        task: str = "task b"

        async def run(self, ctx: GraphRunContext[MyState]) -> End:
            agent = registry.create("b", tool_registry)
            result = await agent.run("task b", model=make_handler("B result"))
            ctx.state.results.append(result.output)
            return End(" | ".join(ctx.state.results))

    class NodeA(AgentNode[MyState]):
        agent_name: str = "a"
        task: str = "task a"

        async def run(self, ctx: GraphRunContext[MyState]) -> NodeB:
            agent = registry.create("a", tool_registry)
            result = await agent.run("task a", model=make_handler("A result"))
            ctx.state.results.append(result.output)
            return NodeB()

    wf = GraphWorkflow(registry=registry, tool_registry=tool_registry)
    result = await wf.run(NodeA(), MyState(query="test"), model=make_handler())

    assert isinstance(result, GraphResult)
    assert "A result" in result.output
    assert "B result" in result.output


@pytest.mark.asyncio
async def test_workflow_error_on_node_failure(registry, tool_registry):
    """Node failure raises WorkflowError."""
    from easyagents.core.exceptions import WorkflowError

    class MyState(TestState):
        pass

    class FailingNode(BaseNode[MyState]):
        async def run(self, ctx: GraphRunContext[MyState]) -> End:
            raise RuntimeError("Node crashed")

    wf = GraphWorkflow(registry=registry, tool_registry=tool_registry)
    with pytest.raises(WorkflowError):
        await wf.run(FailingNode(), MyState(query="test"))
```

- [ ] **Step 2: Run test to verify it fails**

```bash
.venv/bin/python -m pytest tests/test_graph_workflow.py -v
```

Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Create workflows/__init__.py**

```bash
mkdir -p src/easyagents/workflows
touch src/easyagents/workflows/__init__.py
```

- [ ] **Step 4: Write workflows/nodes.py**

```python
from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic_graph import BaseNode, GraphRunContext, End

StateType = TypeVar("StateType")


class AgentNode(BaseNode[StateType], Generic[StateType]):
    """Base class for graph nodes that execute a registered agent.

    Subclasses must override run() to specify next_node logic.
    """
    agent_name: str
    task: str


class ApprovalNode(BaseNode[StateType], Generic[StateType]):
    """Graph node that pauses execution for human approval.

    Returns PendingApproval via End. The caller resumes with GraphWorkflow.resume().
    """
    prompt: str
    next_node: Any
```

- [ ] **Step 5: Write workflows/graph.py**

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pydantic_ai import RunUsage
from pydantic_graph import BaseNode, GraphRunContext, End

from easyagents.core.exceptions import WorkflowError


@dataclass
class PendingApproval:
    """Returned when graph pauses for approval."""
    prompt: str
    state: Any
    resume_node: Any


@dataclass
class ApprovalResult:
    """User's approval response."""
    approved: bool
    feedback: str = ""


@dataclass
class GraphResult:
    """Final result of graph execution."""
    output: Any
    usage: RunUsage = field(default_factory=RunUsage)
    checkpoints: list[str] = field(default_factory=list)


class GraphWorkflow:
    """Executes a graph of nodes with optional HITL and checkpointing."""

    def __init__(
        self,
        registry: Any = None,
        tool_registry: Any = None,
        checkpoint_manager: Any = None,
    ) -> None:
        self.registry = registry
        self.tool_registry = tool_registry
        self.checkpoint_manager = checkpoint_manager

    async def run(
        self,
        start_node: BaseNode,
        state: Any,
        model: Any = None,
    ) -> GraphResult | PendingApproval:
        """Execute graph from start_node. Returns PendingApproval if paused."""
        ctx = GraphRunContext(state=state, deps=None)
        node = start_node

        while True:
            try:
                result = await node.run(ctx)
            except (WorkflowError,):
                raise
            except Exception as e:
                raise WorkflowError(
                    f"Node {type(node).__name__} failed: {e}"
                ) from e

            if isinstance(result, End):
                data = result.data
                if isinstance(data, PendingApproval):
                    return data
                return GraphResult(output=data)

            node = result

    async def resume(
        self,
        pending: PendingApproval,
        approval: ApprovalResult,
        model: Any = None,
    ) -> GraphResult | PendingApproval:
        """Resume graph after approval."""
        if not approval.approved:
            return GraphResult(
                output=f"Rejected: {approval.feedback}" if approval.feedback else "Rejected",
            )

        return await self.run(pending.resume_node, pending.state, model=model)
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
.venv/bin/python -m pytest tests/test_graph_workflow.py -v
```

Expected: 6 passed

- [ ] **Step 7: Run all tests**

```bash
.venv/bin/python -m pytest tests/ -v
```

Expected: 91 passed (85 + 6)

- [ ] **Step 8: Commit**

```bash
git add src/easyagents/workflows/ tests/test_graph_workflow.py
git commit -m "feat: graph nodes, GraphWorkflow with HITL pause/resume"
```

---

### Task 3: CheckpointManager

**Files:**
- Create: `src/easyagents/workflows/checkpoint.py`
- Create: `tests/test_checkpoint.py`

**Interfaces:**
- Consumes: `SessionStore` (optional), `pydantic.TypeAdapter`
- Produces: `CheckpointManager`, `Checkpoint`

- [ ] **Step 1: Write the failing test**

File `tests/test_checkpoint.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
.venv/bin/python -m pytest tests/test_checkpoint.py -v
```

Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write workflows/checkpoint.py**

```python
import json
import sqlite3
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from pydantic import TypeAdapter


@dataclass
class Checkpoint:
    checkpoint_id: str
    workflow_id: str
    node_name: str
    state: Any
    timestamp: str


class CheckpointManager:
    """Manages graph state checkpoints for rollback and recovery."""

    def __init__(self, store: Any = None) -> None:
        self._store = store
        self._memory: dict[str, Checkpoint] = {}
        self._init_db()

    def _init_db(self) -> None:
        if self._store is None:
            return
        # Access the store's connection if it's a SQLiteSessionStore
        conn = getattr(self._store, "_conn", None)
        if conn is not None:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS checkpoints (
                    checkpoint_id  TEXT PRIMARY KEY,
                    workflow_id    TEXT NOT NULL,
                    node_name      TEXT NOT NULL,
                    state_data     TEXT NOT NULL,
                    timestamp      TEXT NOT NULL DEFAULT (datetime('now'))
                );
            """)

    async def save(self, workflow_id: str, node_name: str, state: Any) -> str:
        checkpoint_id = str(uuid4())
        state_data = TypeAdapter(Any).dump_json(state).decode()
        timestamp = ""

        if self._store is not None:
            conn = getattr(self._store, "_conn", None)
            if conn is not None:
                import datetime
                timestamp = datetime.datetime.now().isoformat()
                conn.execute(
                    "INSERT INTO checkpoints (checkpoint_id, workflow_id, node_name, state_data, timestamp) VALUES (?, ?, ?, ?, ?)",
                    (checkpoint_id, workflow_id, node_name, state_data, timestamp),
                )
                return checkpoint_id

        # Memory fallback
        import datetime
        timestamp = datetime.datetime.now().isoformat()
        cp = Checkpoint(
            checkpoint_id=checkpoint_id,
            workflow_id=workflow_id,
            node_name=node_name,
            state=state,
            timestamp=timestamp,
        )
        self._memory[checkpoint_id] = cp
        return checkpoint_id

    async def load(self, checkpoint_id: str) -> Checkpoint | None:
        if self._store is not None:
            conn = getattr(self._store, "_conn", None)
            if conn is not None:
                cursor = conn.execute(
                    "SELECT checkpoint_id, workflow_id, node_name, state_data, timestamp FROM checkpoints WHERE checkpoint_id = ?",
                    (checkpoint_id,),
                )
                row = cursor.fetchone()
                if row is None:
                    return None
                state = TypeAdapter(Any).validate_json(row[3])
                return Checkpoint(
                    checkpoint_id=row[0],
                    workflow_id=row[1],
                    node_name=row[2],
                    state=state,
                    timestamp=row[4],
                )

        return self._memory.get(checkpoint_id)

    async def list_checkpoints(self, workflow_id: str) -> list[str]:
        if self._store is not None:
            conn = getattr(self._store, "_conn", None)
            if conn is not None:
                cursor = conn.execute(
                    "SELECT checkpoint_id FROM checkpoints WHERE workflow_id = ? ORDER BY timestamp",
                    (workflow_id,),
                )
                return [row[0] for row in cursor.fetchall()]

        return [
            cp_id for cp_id, cp in self._memory.items()
            if cp.workflow_id == workflow_id
        ]

    async def rollback(self, checkpoint_id: str) -> Checkpoint | None:
        return await self.load(checkpoint_id)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/bin/python -m pytest tests/test_checkpoint.py -v
```

Expected: 5 passed

- [ ] **Step 5: Run all tests**

```bash
.venv/bin/python -m pytest tests/ -v
```

Expected: 96 passed (91 + 5)

- [ ] **Step 6: Commit**

```bash
git add src/easyagents/workflows/checkpoint.py tests/test_checkpoint.py
git commit -m "feat: CheckpointManager with memory and SQLite backends"
```

---

### Task 4: DynamicOrchestrator

**Files:**
- Modify: `src/easyagents/patterns/orchestrator.py`
- Create: `tests/test_dynamic_orchestrator.py`

**Interfaces:**
- Consumes: `AgentRegistry`, `ToolRegistry`, `OrchestrationResult`, `OrchestrationError`, `pydantic_ai.Agent`
- Produces: `DynamicOrchestrator`, `DynamicSubtask`

- [ ] **Step 1: Write the failing test**

File `tests/test_dynamic_orchestrator.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
.venv/bin/python -m pytest tests/test_dynamic_orchestrator.py -v
```

Expected: FAIL with `ImportError`

- [ ] **Step 3: Add DynamicOrchestrator to patterns/orchestrator.py**

Append to `src/easyagents/patterns/orchestrator.py`:

```python
import json
from pydantic_ai import Agent


@dataclass
class DynamicSubtask:
    """LLM-generated subtask."""
    agent: str
    task: str
    rationale: str


class DynamicOrchestrator:
    """Decomposes tasks dynamically using LLM, then executes subtasks."""

    def __init__(
        self,
        agents: list[str],
        registry: Any,
        tool_registry: Any,
        model: str = "openai:gpt-4o",
        decomposition_prompt: str = "",
        synthesis_agent: str | None = None,
        context_manager: Any = None,
    ) -> None:
        self.agents = agents
        self.registry = registry
        self.tool_registry = tool_registry
        self.model = model
        self.decomposition_prompt = decomposition_prompt
        self.synthesis_agent = synthesis_agent
        self.context_manager = context_manager

    async def decompose(self, task: str, model: Any = None) -> list[DynamicSubtask]:
        prompt = self._build_decomposition_prompt()
        agent = Agent(model=self.model, system_prompt=prompt)

        run_kwargs: dict[str, Any] = {}
        if model is not None:
            run_kwargs["model"] = model

        result = await agent.run(task, **run_kwargs)
        raw_output = str(result.output).strip()

        try:
            subtask_data = json.loads(raw_output)
        except json.JSONDecodeError as e:
            raise OrchestrationError(
                f"LLM returned invalid JSON for decomposition: {raw_output[:200]}"
            ) from e

        subtasks = []
        for item in subtask_data:
            subtask = DynamicSubtask(
                agent=item["agent"],
                task=item["task"],
                rationale=item.get("rationale", ""),
            )
            if subtask.agent not in self.agents:
                raise OrchestrationError(
                    f"LLM selected unknown agent '{subtask.agent}'. "
                    f"Valid agents: {self.agents}"
                )
            subtasks.append(subtask)

        return subtasks

    async def run(self, task: str, model: Any = None) -> OrchestrationResult:
        subtasks = await self.decompose(task, model=model)

        templates = [
            SubtaskTemplate(agent=s.agent, task_template=s.task)
            for s in subtasks
        ]

        orch = OrchestratorWorker(
            orchestrator_agent="dynamic",
            subtasks=templates,
            registry=self.registry,
            tool_registry=self.tool_registry,
            synthesis_agent=self.synthesis_agent,
            context_manager=self.context_manager,
        )

        return await orch.run(task, params={}, model=model)

    async def run_sequential(self, task: str, model: Any = None) -> OrchestrationResult:
        subtasks = await self.decompose(task, model=model)
        usage = RunUsage()
        results: list[Any] = []
        prev_output = ""

        for subtask in subtasks:
            agent = self.registry.create(subtask.agent, self.tool_registry)
            task_text = subtask.task
            if prev_output:
                task_text = f"{task_text}\n\nPrevious result: {prev_output}"

            run_kwargs: dict[str, Any] = {"usage": usage}
            if model is not None:
                run_kwargs["model"] = model

            try:
                result = await agent.run(task_text, **run_kwargs)
                results.append(result.output)
                prev_output = str(result.output)
            except Exception as e:
                results.append(None)

        if all(r is None for r in results):
            raise OrchestrationError("All sequential subtasks failed")

        output = "\n".join(str(r) for r in results if r is not None)
        return OrchestrationResult(output=output, subtask_results=results, usage=usage)

    def _build_decomposition_prompt(self) -> str:
        if self.decomposition_prompt:
            return self.decomposition_prompt

        lines = [
            "You are a task decomposer. Break the task into subtasks.",
            "Available agents:",
        ]
        for name in self.agents:
            try:
                definition = self.registry.get(name)
                desc = definition.description or name
            except Exception:
                desc = name
            lines.append(f"- {name}: {desc}")
        lines.append('Return JSON array: [{"agent": "...", "task": "...", "rationale": "..."}]')
        lines.append("Return ONLY the JSON, no other text.")
        return "\n".join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/bin/python -m pytest tests/test_dynamic_orchestrator.py -v
```

Expected: 5 passed

- [ ] **Step 5: Run all tests**

```bash
.venv/bin/python -m pytest tests/ -v
```

Expected: 101 passed (96 + 5)

- [ ] **Step 6: Commit**

```bash
git add src/easyagents/patterns/orchestrator.py tests/test_dynamic_orchestrator.py
git commit -m "feat: DynamicOrchestrator with LLM-driven task decomposition"
```

---

### Task 5: Public API + Integration Tests

**Files:**
- Modify: `src/easyagents/__init__.py`
- Create: `tests/test_phase3_integration.py`

- [ ] **Step 1: Update __init__.py**

Add imports:

```python
from easyagents.workflows.nodes import AgentNode, ApprovalNode
from easyagents.workflows.graph import GraphWorkflow, GraphResult, PendingApproval, ApprovalResult
from easyagents.workflows.checkpoint import CheckpointManager, Checkpoint
from easyagents.patterns.orchestrator import DynamicOrchestrator, DynamicSubtask
from easyagents.core.exceptions import WorkflowError, CheckpointError, ApprovalError
```

Add to `__all__`:

```python
    # Phase 3 (new)
    "AgentNode",
    "ApprovalNode",
    "GraphWorkflow",
    "GraphResult",
    "PendingApproval",
    "ApprovalResult",
    "CheckpointManager",
    "Checkpoint",
    "DynamicOrchestrator",
    "DynamicSubtask",
    "WorkflowError",
    "CheckpointError",
    "ApprovalError",
```

- [ ] **Step 2: Verify imports**

```bash
.venv/bin/python -c "
from easyagents import (
    AgentNode, ApprovalNode, GraphWorkflow, GraphResult,
    PendingApproval, ApprovalResult, CheckpointManager, Checkpoint,
    DynamicOrchestrator, DynamicSubtask,
    WorkflowError, CheckpointError, ApprovalError,
)
print('All Phase 3 symbols OK')
"
```

- [ ] **Step 3: Write integration tests**

File `tests/test_phase3_integration.py`:

```python
import pytest
from pydantic import BaseModel
from pydantic_ai import ModelResponse, TextPart, RunUsage
from pydantic_ai.models.function import FunctionModel, AgentInfo
from pydantic_graph import BaseNode, GraphRunContext, End

from easyagents import (
    AgentDefinition, AgentRegistry, ToolRegistry,
    GraphWorkflow, GraphResult, PendingApproval, ApprovalResult,
    DynamicOrchestrator,
)


class WorkflowState(BaseModel):
    query: str = ""
    results: list[str] = []
    usage: RunUsage = None

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if self.usage is None:
            self.usage = RunUsage()


def make_handler(output: str = "OK"):
    def handler(messages, info: AgentInfo) -> ModelResponse:
        return ModelResponse(parts=[TextPart(content=output)])
    return FunctionModel(handler)


@pytest.mark.asyncio
async def test_graph_workflow_with_approval_end_to_end():
    """Full flow: agent node -> approval -> resume -> final node."""
    tools = ToolRegistry()
    agents = AgentRegistry()
    agents.register(AgentDefinition(name="worker", instructions="Work.", model="test"))

    class State(WorkflowState):
        pass

    class FinalNode(BaseNode[State]):
        async def run(self, ctx: GraphRunContext[State]) -> End:
            return End("completed successfully")

    class WorkNode(BaseNode[State]):
        async def run(self, ctx: GraphRunContext[State]) -> "ApprovalNode[State]":
            agent = agents.create("worker", tools)
            result = await agent.run("do work", model=make_handler("Work done"))
            ctx.state.results.append(result.output)
            return ApprovalNode(prompt="Approve work?", next_node=FinalNode())

    class ApprovalNode(BaseNode[State]):
        prompt: str
        next_node: BaseNode[State]

        async def run(self, ctx: GraphRunContext[State]) -> End:
            return End(PendingApproval(
                prompt=self.prompt,
                state=ctx.state,
                resume_node=self.next_node,
            ))

    wf = GraphWorkflow(registry=agents, tool_registry=tools)

    # Run -> pauses at approval
    result = await wf.run(WorkNode(), State(query="test"), model=make_handler("Work done"))
    assert isinstance(result, PendingApproval)
    assert "Work done" in result.state.results

    # Resume after approval
    final = await wf.resume(result, ApprovalResult(approved=True), model=make_handler())
    assert isinstance(final, GraphResult)
    assert final.output == "completed successfully"


@pytest.mark.asyncio
async def test_dynamic_orchestrator_end_to_end():
    """Full flow: decompose -> parallel execution."""
    import json

    tools = ToolRegistry()
    agents = AgentRegistry()
    agents.register(AgentDefinition(name="researcher", instructions="Research.", model="test", description="调研"))
    agents.register(AgentDefinition(name="writer", instructions="Write.", model="test", description="写作"))

    subtasks_json = json.dumps([
        {"agent": "researcher", "task": "Find data", "rationale": "Need data"},
        {"agent": "writer", "task": "Write it up", "rationale": "Need report"},
    ])

    def handler(messages, info: AgentInfo) -> ModelResponse:
        content = str(getattr(messages[-1].parts[-1], "content", ""))
        if "decomposer" in content.lower() or "Break" in content:
            return ModelResponse(parts=[TextPart(content=subtasks_json)])
        return ModelResponse(parts=[TextPart(content="Subtask done")])

    dyn = DynamicOrchestrator(
        agents=["researcher", "writer"],
        registry=agents,
        tool_registry=tools,
        model="test",
    )

    result = await dyn.run("调研并写报告", model=FunctionModel(handler))

    assert len(result.subtask_results) == 2


@pytest.mark.asyncio
async def test_checkpoint_with_graph_workflow():
    """CheckpointManager saves state during graph execution."""
    from easyagents import CheckpointManager

    tools = ToolRegistry()
    agents = AgentRegistry()
    agents.register(AgentDefinition(name="worker", instructions="Work.", model="test"))

    mgr = CheckpointManager()

    class State(WorkflowState):
        pass

    class SimpleNode(BaseNode[State]):
        async def run(self, ctx: GraphRunContext[State]) -> End:
            agent = agents.create("worker", tools)
            result = await agent.run("work", model=make_handler("Done"))
            ctx.state.results.append(result.output)
            await mgr.save("wf-1", "SimpleNode", ctx.state)
            return End("finished")

    wf = GraphWorkflow(registry=agents, tool_registry=tools, checkpoint_manager=mgr)
    result = await wf.run(SimpleNode(), State(query="test"), model=make_handler("Done"))

    assert result.output == "finished"
    checkpoints = await mgr.list_checkpoints("wf-1")
    assert len(checkpoints) == 1
    cp = await mgr.load(checkpoints[0])
    assert "Done" in str(cp.state)
```

- [ ] **Step 4: Run all tests**

```bash
.venv/bin/python -m pytest tests/ -v
```

Expected: 104 passed (101 + 3)

- [ ] **Step 5: Run demo**

```bash
.venv/bin/python scripts/demo.py
```

Expected: `Done!`

- [ ] **Step 6: Commit**

```bash
git add src/easyagents/__init__.py tests/test_phase3_integration.py
git commit -m "feat: wire Phase 3 public API and add integration tests"
```
