# EasyAgents Phase 2 - Orchestrator-Worker, Handoff, and Router Patterns

> Date: 2026-07-30
>
> Status: Draft
>
> Depends on: Phase 1.5 - complete (63 tests passing)

## 1. Overview

Phase 2 adds three multi-agent orchestration patterns to the EasyAgents SDK:

1. **OrchestratorWorker** - Parallel subtask execution with predefined templates
2. **HandoffPattern** - Sequential agent switching with configurable context transfer
3. **RouterPattern** - LLM-based intent classification for agent routing

All three patterns are independent classes in `patterns/`, following the existing `DelegationManager` design philosophy.

### 1.1 Design Principles

- **Pattern classes, not config** - Each pattern is a class the developer creates and calls explicitly
- **AgentDefinition unchanged** - Patterns are decoupled from agent definitions
- **Composable** - RouterPattern can route to an OrchestratorWorker; HandoffPattern can use ContextManager
- **Testable** - All patterns accept `model` override for FunctionModel/TestModel testing
- **No new dependencies** - Built entirely on existing pydantic-ai, asyncio, pydantic

### 1.2 Architecture

```
┌─────────────────────────────────────────────────────┐
│                 Public API (__init__.py)              │
├──────────────┬──────────────┬───────────────────────┤
│  Orchestrator│  Handoff     │      Router           │
│  Worker      │  Pattern     │      Pattern          │
│  (parallel)  │  (sequential)│      (LLM routing)    │
├──────────────┴──────────────┴───────────────────────┤
│              Patterns Layer (Phase 2)                 │
│  DelegationManager (MVP) - sequential parent->child   │
├───────────────────────────────────────────────────────┤
│                 SDK Core (MVP + 1.5)                  │
│  AgentRegistry . ToolRegistry . SessionManager        │
│  ContextManager . SessionStore (memory/sqlite)        │
├───────────────────────────────────────────────────────┤
│                   Pydantic AI                         │
└───────────────────────────────────────────────────────┘
```

## 2. Module Structure

```
easyagents/
├── patterns/
│   ├── __init__.py
│   ├── delegation.py         # existing (MVP)
│   ├── orchestrator.py       # NEW: OrchestratorWorker, SubtaskTemplate, OrchestrationResult
│   ├── handoff.py            # NEW: HandoffPattern, HandoffResult
│   └── router.py             # NEW: RouterPattern
├── core/
│   ├── exceptions.py         # +OrchestrationError, HandoffError, RoutingError
│   └── ...                   # unchanged
├── context/
│   └── manager.py            # existing (Phase 1.5), reused by patterns
└── ...
```

## 3. OrchestratorWorker

### 3.1 Overview

Executes predefined subtask templates in parallel across multiple subagents, then optionally synthesizes results.

### 3.2 Data Structures

```python
from dataclasses import dataclass, field
from typing import Any
from pydantic_ai import RunUsage


@dataclass
class SubtaskTemplate:
    """A predefined subtask for parallel execution."""
    agent: str                    # Subagent name (registered in AgentRegistry)
    task_template: str            # Task template with {param} placeholders
    description: str = ""         # Human-readable description


@dataclass
class OrchestrationResult:
    """Result of orchestrator-worker execution."""
    output: Any                    # Final output (synthesized or joined)
    subtask_results: list[Any]     # Individual subtask outputs
    usage: RunUsage                # Aggregated token usage
```

### 3.3 API

```python
class OrchestratorWorker:
    def __init__(
        self,
        orchestrator_agent: str,
        subtasks: list[SubtaskTemplate],
        registry: AgentRegistry,
        tool_registry: ToolRegistry,
        synthesis_agent: str | None = None,
        context_manager: ContextManager | None = None,
    ): ...

    async def run(
        self,
        user_input: str,
        params: dict[str, str] | None = None,
        model: Any = None,
    ) -> OrchestrationResult:
        """Execute the orchestration flow.

        1. Fill subtask templates with params
        2. Run all subtasks in parallel via asyncio.gather
        3. If synthesis_agent is set, synthesize results
        4. Return OrchestrationResult
        """
```

### 3.4 Execution Flow

```
run(user_input="调研蓝牙耳机", params={"topic": "蓝牙耳机"})
  |
  +-- Fill templates:
  |     SubtaskTemplate(agent="researcher", task="Research {topic}")
  |     -> "Research 蓝牙耳机"
  |     SubtaskTemplate(agent="analyst", task="Analyze {topic} market")
  |     -> "Analyze 蓝牙耳机 market"
  |
  +-- Parallel execution (asyncio.gather):
  |     researcher.run("Research 蓝牙耳机")  -> result_1
  |     analyst.run("Analyze 蓝牙耳机 market") -> result_2
  |
  +-- Synthesis (optional):
  |     If synthesis_agent is set:
  |       synthesizer.run(f"Synthesize: {result_1}, {result_2}") -> final
  |     Else:
  |       final = "\n".join(str(r) for r in results)
  |
  +-- Return OrchestrationResult(
        output=final,
        subtask_results=[result_1, result_2],
        usage=aggregated_usage,
      )
```

### 3.5 Error Handling

- **Subtask failure**: The failed subtask's result is set to `None`. Other subtasks continue execution (no interruption). The failure is logged.
- **All subtasks fail**: Raises `OrchestrationError` with details of all failures.
- **Synthesis failure**: Falls back to joining subtask results as strings. Logs a warning.
- **Template parameter missing**: Raises `OrchestrationError` at fill time (before any agent runs).

### 3.6 Usage Tracking

All subagent runs share a single `RunUsage` instance (passed via `usage=` parameter to each `agent.run()`), so the final `OrchestrationResult.usage` includes all subagent and synthesis token consumption.

### 3.7 Context Manager Integration

If `context_manager` is provided, each subtask result is compressed before being passed to the synthesis agent. This prevents token explosion when subtasks return large outputs.

```python
# In synthesis step:
if self._context_manager:
    compressed = await self._context_manager.compress_if_needed(
        subtask_messages, model=model
    )
    # Use compressed messages for synthesis input
```

## 4. HandoffPattern

### 4.1 Overview

Executes a chain of agents sequentially, transferring conversation history between them. Unlike delegation, control is fully transferred - the previous agent does not wait.

### 4.2 Data Structures

```python
@dataclass
class HandoffResult:
    """Result of handoff chain execution."""
    output: Any                  # Last agent's output
    agent_chain: list[str]       # Agents executed in order
    total_messages: int          # Cumulative message count
    usage: RunUsage              # Aggregated token usage
```

### 4.3 API

```python
class HandoffPattern:
    def __init__(
        self,
        agents: list[str],
        registry: AgentRegistry,
        tool_registry: ToolRegistry,
        context_mode: str = "full",        # "full" | "compressed" | "none"
        context_manager: ContextManager | None = None,
        task_templates: list[str] | None = None,  # Optional per-agent tasks
    ): ...

    async def run(
        self,
        user_input: str,
        model: Any = None,
    ) -> HandoffResult:
        """Execute the agent chain sequentially with history transfer."""
```

### 4.4 Execution Flow

```
run(user_input="写一篇蓝牙耳机调研报告")
  |
  +-- Step 1: agents[0] (intake)
  |    agent.run(user_input)
  |    -> messages_1 = result.all_messages()
  |
  +-- Context processing (by context_mode):
  |    "full"       -> history = messages_1
  |    "compressed" -> history = await ctx_mgr.compress_if_needed(messages_1)
  |    "none"       -> history = []
  |
  +-- Step 2: agents[1] (researcher)
  |    task = task_templates[1] or "Continue based on the previous conversation."
  |    agent.run(task, message_history=history)
  |    -> messages_2 = result.all_messages()
  |
  +-- Context processing -> history = process(messages_2)
  |
  +-- Step 3: agents[2] (writer)
  |    task = task_templates[2] or "Continue based on the previous conversation."
  |    agent.run(task, message_history=history)
  |    -> final_output
  |
  +-- Return HandoffResult(
        output=final_output,
        agent_chain=["intake", "researcher", "writer"],
        total_messages=...,
        usage=aggregated_usage,
      )
```

### 4.5 Design Decisions

- **First agent** receives `user_input` directly (or `task_templates[0]` if provided).
- **Subsequent agents** receive their `task_templates[i]` or a default prompt: `"Continue based on the previous conversation."`
- **`task_templates` length** must match `agents` length if provided. Mismatch raises `ValueError` at construction.
- **context_mode="compressed" without context_manager**: Raises `HandoffError` at runtime (configuration error, fail fast).

### 4.6 Error Handling

- **Agent failure mid-chain**: Raises `HandoffError` with the failing agent's name and the original exception.
- **ContextManager failure during compression**: Propagates as `ContextCompressionError` (from Phase 1.5).
- **Empty agent chain**: Raises `ValueError` at construction.

## 5. RouterPattern

### 5.1 Overview

Uses an LLM to classify user intent and route to the most appropriate registered agent.

### 5.2 API

```python
class RouterPattern:
    def __init__(
        self,
        agents: list[str],
        registry: AgentRegistry,
        tool_registry: ToolRegistry,
        model: str = "openai:gpt-4o",
        routing_prompt: str = "",
    ): ...

    async def route(
        self,
        user_input: str,
        model: Any = None,
    ) -> str:
        """Analyze user input, return the best agent name."""

    async def run(
        self,
        user_input: str,
        model: Any = None,
    ) -> Any:
        """Route + execute: route first, then run the selected agent."""
```

### 5.3 Routing Flow

```
run(user_input="帮我 debug 这段 Python 代码")
  |
  +-- Step 1: Build routing prompt
  |    System prompt (auto-generated from agent descriptions):
  |      "You are a router. Given the user input, select the best agent.
  |       Available agents:
  |       - researcher: 产品调研员，使用 web search 调研市场信息
  |       - coder: 编写和调试代码
  |       - writer: 撰写文档和报告
  |       Respond with ONLY the agent name, nothing else."
  |
  +-- Step 2: Route via LLM
  |    router_agent.run(user_input)
  |    -> raw_output = "coder"
  |    -> agent_name = raw_output.strip()
  |
  +-- Step 3: Validate
  |    agent_name in candidates? -> No: raise RoutingError
  |
  +-- Step 4: Execute
  |    selected_agent = registry.create(agent_name, tool_registry)
  |    result = await selected_agent.run(user_input, model=model)
  |
  +-- Return result.output
```

### 5.4 Design Decisions

- **Routing prompt auto-generated**: Built from `AgentRegistry.get(name).description` for each candidate agent. Developers don't need to manually list agent capabilities.
- **`routing_prompt` override**: If provided, replaces the auto-generated prompt entirely. For custom routing logic.
- **`route()` and `run()` separated**: Developers can route without executing (e.g., to confirm with the user first).
- **Router LLM is separate from agent LLMs**: The router uses `self.model` (or `model` override), agent execution uses the agent's own model.

### 5.5 Error Handling

- **LLM returns invalid agent name**: Raises `RoutingError` with the raw LLM output for debugging.
- **Empty agent list**: Raises `ValueError` at construction.
- **Selected agent execution failure**: Exception propagates directly to the caller.
- **Agent with no description**: Uses the agent name as the description in the routing prompt.

## 6. New Exceptions

```python
# core/exceptions.py (additions)

class OrchestrationError(EasyAgentsError):
    """Raised when orchestrator-worker execution fails."""

class HandoffError(EasyAgentsError):
    """Raised when a handoff between agents fails."""

class RoutingError(EasyAgentsError):
    """Raised when agent routing fails (no match, LLM error)."""
```

## 7. Public API

New exports added to `__init__.py`:

```python
# Patterns
from easyagents.patterns.orchestrator import OrchestratorWorker, SubtaskTemplate, OrchestrationResult
from easyagents.patterns.handoff import HandoffPattern, HandoffResult
from easyagents.patterns.router import RouterPattern

# Exceptions
from easyagents.core.exceptions import OrchestrationError, HandoffError, RoutingError
```

Updated `__all__` totals 29 symbols (22 existing + 7 new).

## 8. Dependencies

No new dependencies. Phase 2 builds entirely on:
- pydantic-ai (Agent, RunUsage, RunContext)
- asyncio (asyncio.gather for parallel execution)
- pydantic (dataclasses)
- Existing Phase 1.5 ContextManager

## 9. Testing Strategy

### 9.1 New Test Files

| File | Coverage |
|------|----------|
| `test_orchestrator.py` | Template filling, parallel execution, synthesis, partial failure degradation, total failure raises error, missing param error |
| `test_handoff.py` | Full history transfer, compressed mode, none mode, multi-agent chain, mid-chain failure, missing context_manager error, task_templates |
| `test_router.py` | Normal routing, route + execute, invalid agent name raises error, empty agent list, custom routing_prompt |
| `test_phase2_integration.py` | OrchestratorWorker end-to-end, HandoffPattern + ContextManager, RouterPattern -> OrchestratorWorker composition |

### 9.2 Testing Approach

- **OrchestratorWorker**: FunctionModel simulates each subagent returning fixed results. Parallelism verified via asyncio.sleep delays (total time < sum of individual times).
- **HandoffPattern**: FunctionModel simulates agent chain. Verify `message_history` grows between agents (handler checks received message count).
- **RouterPattern**: FunctionModel simulates router LLM returning agent name string. Verify routing result and subsequent execution.
- **All tests use FunctionModel/TestModel** - no real LLM API calls.

### 9.3 Expected Test Count

| Module | New Tests |
|--------|-----------|
| OrchestratorWorker | ~6 |
| HandoffPattern | ~6 |
| RouterPattern | ~5 |
| Integration | ~3 |
| **Total new** | **~20** |
| **Total (with existing 63)** | **~83** |

## 10. Composability Examples

### Router -> OrchestratorWorker

```python
# Route user query, then orchestrate if needed
router = RouterPattern(
    agents=["simple_qa", "research_orchestrator"],
    registry=agents,
    tool_registry=tools,
)

# The "research_orchestrator" agent can itself be the entry point
# for an OrchestratorWorker pattern
```

### HandoffPattern with Context Compression

```python
handoff = HandoffPattern(
    agents=["intake", "researcher", "writer"],
    registry=agents,
    tool_registry=tools,
    context_mode="compressed",
    context_manager=ContextManager(model="openai:gpt-4o", max_tokens=4000),
)

result = await handoff.run("写一篇蓝牙耳机调研报告")
```

### OrchestratorWorker with Synthesis

```python
orch = OrchestratorWorker(
    orchestrator_agent="coordinator",
    subtasks=[
        SubtaskTemplate(agent="researcher", task_template="Research {topic}"),
        SubtaskTemplate(agent="analyst", task_template="Analyze {topic} market trends"),
    ],
    registry=agents,
    tool_registry=tools,
    synthesis_agent="summarizer",
)

result = await orch.run("调研蓝牙耳机", params={"topic": "蓝牙耳机"})
```

## 11. Out of Scope (Phase 3+)

- Graph-based state machine (Pydantic Graph integration)
- HITL (pause/resume/approval workflows)
- Dynamic task decomposition (LLM decides subtask count and content at runtime)
- Parallel handoff (branching agent chains)
- CLI
- FastAPI backend
- Web UI
