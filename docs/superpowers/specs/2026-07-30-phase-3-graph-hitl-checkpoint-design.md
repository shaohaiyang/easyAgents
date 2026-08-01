# EasyAgents Phase 3 - Graph State Machine, HITL, Checkpoints, and Dynamic Decomposition

> Date: 2026-07-30
>
> Status: Draft
>
> Depends on: Phase 2 - complete (85 tests passing)

## 1. Overview

Phase 3 adds four capabilities to the EasyAgents SDK:

1. **Graph state machine** - Native `pydantic_graph` integration with `AgentNode` and `ApprovalNode` helpers
2. **HITL approval** - Pause/resume pattern via `PendingApproval` return + `resume()` re-invoke
3. **Checkpoint/rollback** - Save graph state after each node, rollback on failure
4. **Dynamic task decomposition** - LLM-driven subtask generation with `DynamicOrchestrator`

### 1.1 Design Principles

- **Native pydantic_graph** - Developers use `BaseNode`, `Edge`, `Graph` directly; SDK provides convenience nodes
- **Return + re-invoke HITL** - Graph pauses by returning `PendingApproval`; caller resumes with `resume()`; no held connections
- **Manual rollback** - Failures raise `WorkflowError` mentioning available checkpoints; caller decides whether to rollback
- **Composable** - DynamicOrchestrator delegates to OrchestratorWorker for parallel execution; GraphWorkflow integrates with CheckpointManager

### 1.2 Architecture

```
┌─────────────────────────────────────────────────────┐
│                 Public API (__init__.py)              │
├──────────────┬──────────────┬───────────────────────┤
│   Workflows  │  Dynamic     │      Exceptions       │
│  GraphWorkflow│  Orchestrator│  WorkflowError etc.  │
│  AgentNode   │              │                       │
│  ApprovalNode│              │                       │
│  Checkpoint  │              │                       │
├──────────────┴──────────────┴───────────────────────┤
│              Patterns Layer (Phase 2)                 │
│  OrchestratorWorker . HandoffPattern . RouterPattern  │
├───────────────────────────────────────────────────────┤
│                 SDK Core (MVP + 1.5)                  │
├───────────────────────────────────────────────────────┤
│              pydantic_graph + Pydantic AI             │
└───────────────────────────────────────────────────────┘
```

## 2. Module Structure

```
easyagents/
├── workflows/               # NEW
│   ├── __init__.py
│   ├── nodes.py             # AgentNode, ApprovalNode
│   ├── graph.py             # GraphWorkflow, GraphResult, PendingApproval, ApprovalResult
│   └── checkpoint.py        # CheckpointManager, Checkpoint
├── patterns/
│   ├── orchestrator.py      # MODIFY: add DynamicOrchestrator, DynamicSubtask
│   └── ...
├── core/
│   └── exceptions.py        # +WorkflowError, CheckpointError, ApprovalError
└── ...
```

## 3. Graph Nodes

### 3.1 AgentNode

Wraps agent execution as a graph node. Automatically connects to AgentRegistry.

```python
from pydantic_graph import BaseNode, GraphRunContext, End
from pydantic import BaseModel
from typing import TypeVar, Generic

StateType = TypeVar("StateType")


class AgentNode(BaseNode[StateType]):
    """Graph node that runs a registered agent."""
    agent_name: str
    task: str
    next_node: BaseNode[StateType] | None = None
```

**Execution:** `AgentNode.run()` calls `registry.create(agent_name, tool_registry)`, then `agent.run(task)`, stores the output in `ctx.state`, and returns `next_node` or `End`.

**State contract:** The state object must have a `results: list` field (or similar) for storing agent outputs. The node appends `result.output` to `ctx.state.results`.

### 3.2 ApprovalNode

Pauses graph execution for human approval. Returns `PendingApproval` via `End`.

```python
class ApprovalNode(BaseNode[StateType]):
    """Graph node that pauses execution for human approval."""
    prompt: str                              # Displayed to user
    next_node: BaseNode[StateType]           # Executed after approval
```

**Execution:** `ApprovalNode.run()` returns `End(result=PendingApproval(prompt=..., state=ctx.state, resume_node=next_node))`. The graph run stops, returning the `PendingApproval` to the caller.

## 4. GraphWorkflow + HITL

### 4.1 Data Structures

```python
@dataclass
class PendingApproval:
    """Returned when graph pauses for approval."""
    prompt: str                    # Approval prompt for user
    state: Any                     # Current graph state (serializable)
    resume_node: Any               # Node to execute after approval

@dataclass
class ApprovalResult:
    """User's approval response."""
    approved: bool                 # True=approved, False=rejected
    feedback: str = ""             # Optional feedback

@dataclass
class GraphResult:
    """Final result of graph execution."""
    output: Any                    # Final output
    usage: RunUsage                # Aggregated token usage
    checkpoints: list[str]         # Checkpoint IDs created during run
```

### 4.2 GraphWorkflow API

```python
class GraphWorkflow:
    def __init__(
        self,
        graph: Graph,
        registry: AgentRegistry,
        tool_registry: ToolRegistry,
        checkpoint_manager: CheckpointManager | None = None,
    ): ...

    async def run(
        self,
        start_node: BaseNode,
        state: Any,
        model: Any = None,
    ) -> GraphResult | PendingApproval:
        """Execute graph. Returns PendingApproval if an ApprovalNode is reached."""

    async def resume(
        self,
        pending: PendingApproval,
        approval: ApprovalResult,
        model: Any = None,
    ) -> GraphResult | PendingApproval:
        """Resume after approval. May return another PendingApproval."""
```

### 4.3 Execution Flow

```
run(start_node=ResearchNode, state=MyState(query="test"))
  |
  +-- ResearchNode.run() -> agent executes -> returns ApprovalNode
  +-- Checkpoint saved (if checkpoint_manager configured)
  +-- ApprovalNode.run() -> returns End(PendingApproval)
  +-- Returns PendingApproval(prompt, state, resume_node)

Caller reviews:
  approval = ApprovalResult(approved=True)

resume(pending, approval)
  |
  +-- If approved: continue from resume_node
  +-- SynthesisNode.run() -> agent executes -> returns End
  +-- Returns GraphResult(output, usage, checkpoints)

If rejected (approved=False):
  +-- Returns GraphResult(output=feedback, usage, checkpoints=[])
```

### 4.4 Rejection Handling

When `approval.approved=False`, `resume()` does not execute `resume_node`. It returns `GraphResult` with `output=f"Rejected: {approval.feedback}"` and empty checkpoints for this segment.

### 4.5 Multiple Approvals

If the graph has multiple `ApprovalNode`s, `resume()` may return another `PendingApproval`. The caller calls `resume()` repeatedly until a `GraphResult` is returned.

## 5. Checkpoint/Rollback

### 5.1 CheckpointManager

```python
class CheckpointManager:
    def __init__(self, store: SessionStore | None = None): ...

    async def save(self, workflow_id: str, node_name: str, state: Any) -> str: ...
    async def load(self, checkpoint_id: str) -> Checkpoint | None: ...
    async def list_checkpoints(self, workflow_id: str) -> list[str]: ...
    async def rollback(self, checkpoint_id: str) -> Checkpoint: ...
```

### 5.2 Checkpoint Data Structure

```python
@dataclass
class Checkpoint:
    checkpoint_id: str
    workflow_id: str
    node_name: str
    state: Any                    # Serialized graph state
    timestamp: str                # ISO format
```

### 5.3 Storage

- **With SessionStore (SQLite):** Checkpoints stored in a `checkpoints` table:

```sql
CREATE TABLE IF NOT EXISTS checkpoints (
    checkpoint_id  TEXT PRIMARY KEY,
    workflow_id    TEXT NOT NULL,
    node_name      TEXT NOT NULL,
    state_data     TEXT NOT NULL,
    timestamp      TEXT NOT NULL
);
```

- **Without SessionStore (memory):** In-memory dict, process-lifetime only.
- **State serialization:** Pydantic `TypeAdapter` to JSON (consistent with message serialization).

### 5.4 Integration with GraphWorkflow

- After each node execution, if `checkpoint_manager` is set, saves checkpoint
- On node failure, raises `WorkflowError` mentioning checkpoint availability
- Rollback is manual: caller catches `WorkflowError`, loads checkpoint, re-runs from saved state

### 5.5 Design Decisions

- **Manual rollback** (not automatic): Avoids unintended side effects from automatic retries
- **Per-node granularity**: One checkpoint per node execution. Simple and sufficient.
- **Workflow ID**: Caller provides a unique ID per graph run for checkpoint isolation

## 6. DynamicOrchestrator

### 6.1 Overview

Uses LLM to decompose a task into subtasks dynamically, then executes them in parallel (or sequentially). Unlike Phase 2's `OrchestratorWorker` (predefined templates), the LLM decides subtask count, agent assignment, and task content.

### 6.2 Data Structures

```python
@dataclass
class DynamicSubtask:
    """LLM-generated subtask."""
    agent: str          # LLM-selected agent name
    task: str           # LLM-generated task description
    rationale: str      # LLM's reasoning for this assignment
```

### 6.3 API

```python
class DynamicOrchestrator:
    def __init__(
        self,
        agents: list[str],
        registry: AgentRegistry,
        tool_registry: ToolRegistry,
        model: str = "openai:gpt-4o",
        decomposition_prompt: str = "",
        synthesis_agent: str | None = None,
        context_manager: ContextManager | None = None,
    ): ...

    async def decompose(self, task: str, model: Any = None) -> list[DynamicSubtask]: ...

    async def run(self, task: str, model: Any = None) -> OrchestrationResult: ...

    async def run_sequential(self, task: str, model: Any = None) -> OrchestrationResult: ...
```

### 6.4 Decomposition Flow

```
decompose(task="调研蓝牙耳机市场并写报告")
  |
  +-- Build prompt from agent descriptions:
  |     "You are a task decomposer. Break the task into subtasks.
  |      Available agents:
  |      - researcher: 调研市场信息
  |      - analyst: 分析市场趋势
  |      - writer: 撰写报告
  |      Return JSON: [{"agent": "...", "task": "...", "rationale": "..."}]"
  |
  +-- LLM returns JSON array
  +-- Parse with Pydantic -> list[DynamicSubtask]
  +-- Validate each agent name against registered agents
  +-- Return list[DynamicSubtask]
```

### 6.5 Execution Modes

**Parallel (`run`):** All subtasks run via `asyncio.gather` (delegates to OrchestratorWorker logic). Results optionally synthesized.

**Sequential (`run_sequential`):** Subtasks run in order. Each subtask receives the previous subtask's output as context. Useful when subtasks have dependencies (e.g., writer needs researcher's output).

### 6.6 Error Handling

- **LLM returns invalid JSON:** Raises `OrchestrationError` with raw LLM output
- **LLM returns unknown agent name:** Raises `OrchestrationError` listing valid agents
- **Subtask execution failure:** Same as OrchestratorWorker (None result, partial degradation)

## 7. New Exceptions

```python
class WorkflowError(EasyAgentsError):
    """Raised when a graph workflow execution fails."""

class CheckpointError(EasyAgentsError):
    """Raised when checkpoint save/load/rollback fails."""

class ApprovalError(EasyAgentsError):
    """Raised when approval resumption fails (invalid state, already resumed)."""
```

## 8. Public API

New exports (11):

```python
from easyagents.workflows.nodes import AgentNode, ApprovalNode
from easyagents.workflows.graph import GraphWorkflow, GraphResult, PendingApproval, ApprovalResult
from easyagents.workflows.checkpoint import CheckpointManager, Checkpoint
from easyagents.patterns.orchestrator import DynamicOrchestrator, DynamicSubtask
from easyagents.core.exceptions import WorkflowError, CheckpointError, ApprovalError
```

`__all__` totals 42 symbols (31 existing + 11 new).

## 9. Dependencies

No new dependencies. Phase 3 builds on:
- `pydantic_graph` (bundled with pydantic-ai)
- `pydantic` (TypeAdapter for serialization)
- `asyncio` (gather for parallel execution)
- Existing Phase 1.5 SessionStore (for checkpoint persistence)

## 10. Testing Strategy

### 10.1 New Test Files

| File | Coverage |
|------|----------|
| `test_graph_nodes.py` | AgentNode executes agent and stores result, ApprovalNode returns PendingApproval |
| `test_graph_workflow.py` | Normal execution to End, pause at ApprovalNode, resume after approval, rejection path, multiple approvals |
| `test_checkpoint.py` | Save/load/list/rollback, memory + SQLite backends, state serialization round-trip |
| `test_dynamic_orchestrator.py` | decompose returns subtask list, run parallel, run_sequential, invalid JSON raises error, unknown agent raises error |
| `test_phase3_integration.py` | GraphWorkflow + ApprovalNode end-to-end, DynamicOrchestrator end-to-end |

### 10.2 Testing Approach

- **Graph nodes:** FunctionModel simulates agent execution; verify state updates
- **HITL:** Verify `run()` returns `PendingApproval`, `resume()` continues, rejection returns feedback
- **Checkpoints:** `:memory:` SQLite; verify save/load/rollback correctness
- **DynamicOrchestrator:** FunctionModel simulates LLM returning JSON subtask list
- **All tests use FunctionModel/TestModel** - no real LLM API calls

### 10.3 Expected Test Count

| Module | New Tests |
|--------|-----------|
| Graph nodes | ~4 |
| GraphWorkflow + HITL | ~6 |
| Checkpoint | ~5 |
| DynamicOrchestrator | ~5 |
| Integration | ~3 |
| **Total new** | **~23** |
| **Total (with existing 85)** | **~108** |

## 11. Out of Scope (Phase 4+)

- CLI
- FastAPI backend
- Web UI
- Automatic rollback with retry policies
- Graph visualization
- Workflow templates / marketplace
- Distributed graph execution
