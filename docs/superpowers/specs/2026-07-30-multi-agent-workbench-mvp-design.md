# EasyAgents Multi-Agent Workbench - MVP Design

> Date: 2026-07-30
>
> Status: Draft

## 1. Project Overview

### 1.1 Goal

Build a general-purpose multi-agent workbench SDK where developers can define, orchestrate, run, and observe multi-agent workflows. The system is built on top of Pydantic AI, wrapping its native capabilities with a registry-based, declarative configuration layer.

### 1.2 Design References

- [Anthropic: How we built our multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system) - orchestrator-worker pattern, parallel subagents, artifact system, token scaling
- [GitHub: What are multi-agent systems?](https://github.com/resources/articles/what-are-multi-agent-systems) - design patterns (subagent, router, handoff, skills), lifecycle, reliability engineering
- [Pydantic AI: Messages and chat history](https://pydantic.dev/docs/ai/core-concepts/message-history/) - message_history, conversation_id/run_id, ProcessHistory, serialization
- [Pydantic AI: Multi-agent applications](https://pydantic.dev/docs/ai/guides/multi-agent-applications/) - agent delegation, programmatic handoff, graph-based control flow, deep agents

### 1.3 Architecture Approach

Layered SDK with incremental patterns (Approach A from brainstorming). The SDK core is built first; multi-agent patterns, CLI, API, and Web UI are added in subsequent phases.

## 2. Scope

### 2.1 MVP Scope (This Spec)

| Included | Excluded (Future Phases) |
|---|---|
| Agent definition & registry | Orchestrator-worker (parallel subagents) |
| Agent delegation (parent calls child via tool) | Programmatic handoff |
| Tool system (web_search built-in + custom registration) | Graph-based state machine |
| In-memory session (message_history) | HITL (pause/resume/approval) |
| Logfire auto-trace observability | SQLite persistence |
| Structured output (Pydantic BaseModel) | CLI |
| | FastAPI backend |
| | Web UI |

### 2.2 Future Phases

```
MVP (this spec)    ->  delegation + web_search + Logfire
Phase 1.5          ->  + SQLite persistence + more tools (http_request, write_file)
Phase 2            ->  + orchestrator-worker (parallel) + programmatic handoff
Phase 3            ->  + graph state machine + HITL
Phase 4            ->  + CLI
Phase 5            ->  + FastAPI + Web UI
```

Each phase gets its own spec -> plan -> implementation cycle.

## 3. Architecture

### 3.1 Layered Architecture

```
┌─────────────────────────────────────────────────────┐
│                    Web UI (Phase 5)                   │
├─────────────────────────────────────────────────────┤
│              FastAPI Backend (Phase 4)                │
├─────────────────────────────────────────────────────┤
│                       CLI (Phase 3)                   │
├──────────────┬──────────────┬───────────────────────┤
│   Patterns   │  Observability│     Persistence        │
│  delegation  │  Logfire      │   SQLite (Phase 1.5)  │
│  (MVP)       │  (MVP)        │                       │
├──────────────┴──────────────┴───────────────────────┤
│                      SDK Core (MVP)                   │
│  AgentRegistry  ·  ToolRegistry  ·  SessionManager    │
│  Config  ·  Exceptions                               │
├─────────────────────────────────────────────────────┤
│                   Pydantic AI                         │
│  Agent  ·  message_history  ·  tools  ·  graph        │
├─────────────────────────────────────────────────────┤
│          LLM Providers (OpenAI, Anthropic, Google)    │
└─────────────────────────────────────────────────────┘
```

### 3.2 Module Structure (MVP)

```
easyagents/
├── __init__.py              # Public API exports
├── core/
│   ├── __init__.py
│   ├── agent.py             # AgentDefinition, AgentRegistry
│   ├── session.py           # Session, SessionManager (in-memory)
│   ├── config.py            # Global configuration
│   └── exceptions.py        # Workbench-specific exceptions
├── tools/
│   ├── __init__.py
│   ├── registry.py          # ToolRegistry
│   ├── base.py              # ToolMetadata, Tool protocol
│   └── builtin/
│       ├── __init__.py
│       └── web_search.py    # Built-in web search tool
├── patterns/
│   ├── __init__.py
│   └── delegation.py        # Agent delegation pattern
└── observability/
    ├── __init__.py
    └── tracing.py           # Logfire integration
```

## 4. Core Abstractions

### 4.1 AgentDefinition

Declarative agent configuration, decoupled from Pydantic AI `Agent` instantiation. An `AgentDefinition` is a data recipe; `AgentRegistry.create()` turns it into a live `pydantic_ai.Agent`.

```python
from dataclasses import dataclass, field
from typing import Any

@dataclass
class AgentDefinition:
    name: str                          # Unique identifier, used in subagents references
    instructions: str                  # System prompt / instructions for the agent
    model: str                         # Pydantic AI model string, e.g. "openai:gpt-4o"
    tools: list[str] = field(default_factory=list)   # Tool names from ToolRegistry
    output_type: type | None = None    # Structured output schema (Pydantic BaseModel)
    deps_type: type | None = None      # Dependency injection type
    description: str = ""              # Human-readable, used for routing/orchestration
    subagents: list[str] = field(default_factory=list)  # Names of agents this one can delegate to
```

**Design decisions:**

- `subagents` is a list of agent names, not agent objects. This keeps definitions declarative and avoids circular references. The registry resolves names to agents at creation time.
- `tools` and `subagents` can coexist on the same agent. An agent with `tools=["web_search"]` and `subagents=["researcher"]` gets both the `web_search` tool and an auto-injected `delegate_researcher` tool. The `AgentRegistry.create()` method resolves both lists independently and merges them into a single toolset.
- `output_type` uses `None` for free-text output (Pydantic AI default). When set to a `BaseModel` subclass, Pydantic AI enforces structured output.
- `deps_type` is included for forward compatibility with Phase 1.5 (SQLite, HTTP clients). The MVP does not use it but the field exists so adding dependencies later doesn't break the API.

### 4.2 AgentRegistry

Central registry that stores `AgentDefinition` objects and creates Pydantic AI `Agent` instances on demand.

```python
from pydantic_ai import Agent
from typing import Any

class AgentRegistry:
    def __init__(self) -> None: ...

    def register(self, definition: AgentDefinition) -> None
        """Register an agent definition. Raises AgentAlreadyRegisteredError if name exists."""

    def get(self, name: str) -> AgentDefinition
        """Retrieve a registered definition. Raises AgentNotFoundError if not found."""

    def create(self, name: str, tool_registry: ToolRegistry) -> Agent
        """Create a Pydantic AI Agent from the registered definition.
        
        Resolves tool names to Tool objects via tool_registry.
        Injects delegation tools for each name in definition.subagents.
        Caches the created Agent so repeated calls return the same instance.
        """

    def list(self) -> list[str]
        """List all registered agent names."""
```

**Caching:** Created `Agent` instances are cached by name. Pydantic AI agents are designed to be global and stateless, so caching is safe and avoids redundant setup.

**Delegation tool injection:** When `definition.subagents` is non-empty, `create()` automatically registers a delegation tool for each subagent name. See section 4.5 for details.

### 4.3 ToolRegistry

Manages built-in and custom tools. Tools are registered by name and resolved to Pydantic AI tool objects.

```python
from typing import Callable, Any

@dataclass
class ToolMetadata:
    name: str
    description: str
    parameters: dict[str, Any]   # JSON schema for parameters

class ToolRegistry:
    def __init__(self) -> None: ...

    def register(self, name: str, func: Callable, description: str = "") -> None
        """Register a callable as a tool. If description is empty, uses func.__doc__.
        Raises ToolAlreadyRegisteredError if name exists."""

    def resolve(self, names: list[str]) -> list[Tool]
        """Resolve tool names to Pydantic AI Tool objects.
        Raises ToolNotFoundError for any missing name."""

    def get(self, name: str) -> ToolMetadata
        """Get metadata for a registered tool."""

    def list(self) -> list[ToolMetadata]
        """List all registered tools."""
```

**Tool wrapping:** `resolve()` wraps registered callables into Pydantic AI `Tool` objects. It extracts the function signature and docstring to generate the tool schema automatically. For async functions, the wrapper preserves async behavior.

### 4.4 Built-in Tools

#### web_search

```python
async def web_search(query: str, max_results: int = 5) -> list[dict[str, str]]:
    """Search the web and return results.
    
    Args:
        query: Search query string
        max_results: Maximum number of results to return (default 5)
    
    Returns:
        List of dicts with keys: title, url, snippet
    """
```

**Implementation:** Uses DuckDuckGo Search (duckduckgo-search package) as the default search backend. No API key required, making it ideal for MVP. The tool is async to avoid blocking the event loop.

**Error handling:** Network errors return an empty list with a warning log, rather than raising. This follows Anthropic's principle of letting agents adapt to tool failures gracefully.

### 4.5 Delegation Pattern

The simplest multi-agent pattern: a parent agent delegates work to a child agent via an auto-injected tool, then takes back control when the child finishes.

```python
from pydantic_ai import Agent, RunContext
from dataclasses import dataclass

class DelegationManager:
    """Manages delegation from parent agents to child agents.
    
    Created internally by AgentRegistry.create() when definition.subagents is non-empty.
    """

    def __init__(self, parent_name: str, subagent_names: list[str], 
                 registry: AgentRegistry, tool_registry: ToolRegistry) -> None: ...

    def create_delegation_tools(self) -> list[Tool]:
        """Create a Pydantic AI tool for each subagent.
        
        Each tool has the name 'delegate_<subagent_name>' and accepts
        a 'task' parameter (str). When called, it runs the subagent
        with the given task and returns the subagent's output.
        """

    async def delegate(self, subagent_name: str, task: str, 
                       parent_usage: RunUsage) -> Any:
        """Run the subagent with the given task.
        
        Passes parent_usage so child token usage counts toward parent total.
        Returns the subagent's output (str or structured type).
        """
```

**Delegation tool naming:** Tools are named `delegate_<subagent_name>` (e.g., `delegate_researcher`). This avoids collisions with user-registered tools and makes delegation visible in traces.

**Usage tracking:** The parent agent's `RunContext.usage` is passed to the child agent's `Agent.run(usage=...)` call. This ensures the parent's final `result.usage` includes all child agent token usage, following Pydantic AI's delegation pattern.

**Message isolation:** Child agents run with their own message history. They do not inherit the parent's conversation context. This mirrors Anthropic's principle of "separation of concerns - distinct tools, prompts, and exploration trajectories" and prevents context pollution. The child returns only its output to the parent via the tool return value.

### 4.6 Observability

```python
def configure(
    logfire_token: str | None = None,
    service_name: str = "easyagents",
) -> None:
    """Configure observability for the workbench.
    
    Calls logfire.configure() and logfire.instrument_pydantic_ai().
    If logfire_token is None, logs to stderr (development mode).
    If logfire_token is provided, sends traces to Logfire cloud.
    
    This is the single entry point for observability setup.
    No per-agent or per-tool configuration needed.
    """
```

**What gets traced automatically:**
- Each `Agent.run()` call creates a span with agent name, model, token usage
- Tool calls create child spans with tool name, arguments, return value
- Delegation creates nested spans showing parent -> child relationship
- `conversation_id` and `run_id` are propagated as span attributes

**No custom instrumentation code required.** Pydantic AI's built-in Logfire integration handles span creation. The `configure()` function is a convenience wrapper that sets up both Logfire and Pydantic AI instrumentation in one call.

### 4.7 Session (In-Memory)

The MVP uses in-memory message history. No persistence layer.

```python
from pydantic_ai import ModelMessage

@dataclass
class Session:
    conversation_id: str
    messages: list[ModelMessage]

class SessionManager:
    """In-memory session manager. Sessions are lost on process exit.
    
    Phase 1.5 will replace this with SQLite-backed persistence.
    The API surface (create/load/save_messages) stays the same.
    """

    def __init__(self) -> None: ...

    def create(self) -> Session:
        """Create a new session with a generated conversation_id."""

    def get(self, conversation_id: str) -> Session | None:
        """Retrieve a session by conversation_id. Returns None if not found."""

    def save_messages(self, conversation_id: str, messages: list[ModelMessage]) -> None:
        """Update the message history for a session."""
```

**Usage with agent runs:** After an agent run, the caller stores `result.all_messages()` in the session. For follow-up runs, the caller passes `session.messages` as `message_history` to the next `Agent.run()` call. The `conversation_id` from the first run is reused for all subsequent runs in the same session.

## 5. Public API

The `easyagents/__init__.py` exports the following:

```python
from easyagents.core.agent import AgentDefinition, AgentRegistry
from easyagents.core.session import Session, SessionManager
from easyagents.core.exceptions import (
    EasyAgentsError,
    AgentAlreadyRegisteredError,
    AgentNotFoundError,
    ToolAlreadyRegisteredError,
    ToolNotFoundError,
    DelegationError,
)
from easyagents.tools.registry import ToolRegistry, ToolMetadata
from easyagents.tools.builtin.web_search import web_search
from easyagents.observability.tracing import configure

__all__ = [
    "AgentDefinition",
    "AgentRegistry",
    "Session",
    "SessionManager",
    "ToolRegistry",
    "ToolMetadata",
    "web_search",
    "configure",
    "EasyAgentsError",
    "AgentAlreadyRegisteredError",
    "AgentNotFoundError",
    "ToolAlreadyRegisteredError",
    "ToolNotFoundError",
    "DelegationError",
]
```

**SessionManager is optional.** The MVP test case (section 6.3) works without it - agents can be created and run directly. SessionManager is available for users who want to manage multi-turn conversations in memory, and its API is designed so SQLite can replace it in Phase 1.5 without breaking callers.

## 6. Test Case

### 6.1 Scenario

> "调研最近爆火的蓝牙耳机"

Two agents, sequential delegation, validates the minimum multi-agent loop.

### 6.2 Agent Definitions

```python
from pydantic import BaseModel, Field

class ResearchFindings(BaseModel):
    products: list[str] = Field(description="识别到的热门蓝牙耳机产品名称")
    summary: str = Field(description="调研摘要")

agents = AgentRegistry()

agents.register(AgentDefinition(
    name="researcher",
    instructions="你是一个产品调研员。用 web_search 工具调研用户问题，返回结构化的调研发现。",
    model="openai:gpt-4o",
    tools=["web_search"],
    output_type=ResearchFindings,
    description="产品调研员，使用 web search 调研市场信息",
))

agents.register(AgentDefinition(
    name="orchestrator",
    instructions="你是调研编排器。用 delegate_researcher 工具委托调研员调研用户问题，然后总结调研结果。",
    model="openai:gpt-4o",
    tools=[],
    subagents=["researcher"],
    description="调研编排器，委托调研员并总结结果",
))
```

### 6.3 Execution

```python
from easyagents import configure, ToolRegistry, AgentRegistry, AgentDefinition, web_search

configure()  # Logfire auto-trace

tools = ToolRegistry()
tools.register("web_search", web_search)

# ... register agents (see 6.2) ...

agent = agents.create("orchestrator", tools)
result = agent.run_sync("调研最近爆火的蓝牙耳机")
print(result.output)
```

### 6.4 Expected Logfire Trace

```
orchestrator.run  [span] 8.2s  1,850 tokens
├── delegate_researcher(task="调研最近爆火的蓝牙耳机")  [span] 6.1s  1,420 tokens
│   ├── web_search("2025 热门蓝牙耳机")  [span] 0.9s
│   └── web_search("蓝牙耳机 爆款 推荐")  [span] 0.7s
└── synthesize  [span] 1.5s  430 tokens

总计: 8.2s  1,850 tokens  2 runs  1 delegation  2 tool calls
```

### 6.5 Validation Criteria

| Dimension | Check | Pass Condition |
|---|---|---|
| Agent registration | Both agents registered in registry | `agents.list()` returns `["researcher", "orchestrator"]` |
| Tool resolution | web_search resolved to Pydantic AI Tool | No `ToolNotFoundError` |
| Delegation tool injection | `delegate_researcher` tool auto-created | Orchestrator agent has 1 tool: `delegate_researcher` |
| Delegation execution | Orchestrator calls researcher via tool | Trace shows nested span `delegate_researcher` |
| Usage tracking | Child tokens counted in parent | `result.usage.total_tokens` includes researcher's tokens |
| Structured output | Researcher returns `ResearchFindings` | `result.output` is parseable as `ResearchFindings` |
| Message isolation | Researcher has independent context | Researcher's messages not in orchestrator's `all_messages()` |
| Web search | web_search returns results | Tool return value is non-empty list |

## 7. Error Handling

### 7.1 Custom Exceptions

```python
class EasyAgentsError(Exception):
    """Base exception for all EasyAgents errors."""

class AgentAlreadyRegisteredError(EasyAgentsError):
    """Raised when registering an agent with a name that already exists."""

class AgentNotFoundError(EasyAgentsError):
    """Raised when looking up an agent that doesn't exist in the registry."""

class ToolAlreadyRegisteredError(EasyAgentsError):
    """Raised when registering a tool with a name that already exists."""

class ToolNotFoundError(EasyAgentsError):
    """Raised when resolving a tool name that doesn't exist in the registry."""

class DelegationError(EasyAgentsError):
    """Raised when a delegation call fails (subagent crashes, returns invalid output)."""
```

### 7.2 Error Strategy

| Error Source | Strategy |
|---|---|
| Agent/tool registration (duplicate name) | Raise immediately. Configuration errors should fail fast. |
| Agent/tool lookup (not found) | Raise `AgentNotFoundError` / `ToolNotFoundError`. |
| Web search network failure | Return empty list + log warning. Let the agent adapt (Anthropic principle: "letting the agent know when a tool is failing and letting it adapt works surprisingly well"). |
| Subagent crash during delegation | Wrap in `DelegationError` with context (parent name, child name, task). Re-raise to parent agent's tool loop so the parent can decide to retry or report failure. |
| Subagent returns wrong output type | Pydantic AI's structured output validation handles this. The parent agent receives a validation error in the tool return, which it can adapt to. |
| LLM API failure | Pydantic AI's built-in retry logic handles transient API failures. No custom retry needed for MVP. |

### 7.3 No Silent Failures

The MVP does not silently swallow errors. Every error either:
1. Raises an exception (configuration errors, lookups)
2. Returns a degraded result with a logged warning (tool failures like web_search)
3. Propagates to the agent's tool loop as a tool error (delegation failures)

## 8. Testing Strategy

### 8.1 Unit Tests

| Component | What to Test |
|---|---|
| `AgentRegistry` | Register, get, list, duplicate detection, not-found error |
| `ToolRegistry` | Register, resolve, list, duplicate detection, not-found error |
| `AgentRegistry.create()` | Tool resolution, delegation tool injection, agent caching |
| `DelegationManager` | Tool naming, usage tracking, message isolation |
| `SessionManager` | Create, get, save_messages, not-found returns None |
| `web_search` | Returns list of dicts, handles network errors gracefully |
| `configure()` | Does not raise, idempotent |

### 8.2 Integration Test

The test case from section 6, run with a `TestModel` or `FunctionModel` (Pydantic AI's test models) to avoid real LLM API calls:

```python
from pydantic_ai.models.test import TestModel

# Use TestModel to simulate LLM responses without API calls
test_model = TestModel(custom_output_text="调研发现：AirPods Pro 2, Sony WF-1000XM5, Bose QC Ultra")

agent = agents.create("orchestrator", tools)
# Override model with test model for deterministic testing
result = agent.run_sync("调研最近爆火的蓝牙耳机", model=test_model)
```

### 8.3 Test Framework

- **pytest** with `pytest-asyncio` for async tests
- **Pydantic AI TestModel / FunctionModel** for deterministic LLM-free testing
- No real LLM API calls in the test suite

## 9. Dependencies

### 9.1 Required

| Package | Version | Purpose |
|---|---|---|
| `pydantic-ai` | `>=0.0.30` | Agent framework foundation |
| `pydantic` | `>=2.0` | Data validation, structured output |
| `logfire` | `>=3.0` | Observability, tracing |
| `duckduckgo-search` | `>=6.0` | Web search backend (no API key needed) |

### 9.2 Dev Dependencies

| Package | Version | Purpose |
|---|---|---|
| `pytest` | `>=8.0` | Test framework |
| `pytest-asyncio` | `>=0.23` | Async test support |
| `pytest-cov` | `>=5.0` | Coverage reporting |

### 9.3 LLM Provider Packages

Users install the provider packages they need. Pydantic AI auto-detects installed providers:

```bash
pip install pydantic-ai[openai]      # OpenAI
pip install pydantic-ai[anthropic]   # Anthropic
pip install pydantic-ai[google]      # Google Gemini
```

## 10. File Layout

```
easyagents/
├── README.md                    # Existing prompt docs (unchanged)
├── SKILL.md                     # Existing skill docs (unchanged)
├── vibe-coding-prompts.md       # Existing prompts (unchanged)
├── pyproject.toml               # Project config, dependencies
├── docs/
│   └── superpowers/
│       └── specs/
│           └── 2026-07-30-multi-agent-workbench-mvp-design.md  # This document
├── src/
│   └── easyagents/
│       ├── __init__.py          # Public API
│       ├── core/
│       │   ├── __init__.py
│       │   ├── agent.py         # AgentDefinition, AgentRegistry
│       │   ├── session.py       # Session, SessionManager (in-memory)
│       │   ├── config.py        # Configuration
│       │   └── exceptions.py    # Exceptions
│       ├── tools/
│       │   ├── __init__.py
│       │   ├── registry.py      # ToolRegistry, ToolMetadata
│       │   ├── base.py          # Tool protocol
│       │   └── builtin/
│       │       ├── __init__.py
│       │       └── web_search.py
│       ├── patterns/
│       │   ├── __init__.py
│       │   └── delegation.py    # DelegationManager
│       └── observability/
│           ├── __init__.py
│           └── tracing.py       # configure()
└── tests/
    ├── conftest.py
    ├── test_agent_registry.py
    ├── test_tool_registry.py
    ├── test_delegation.py
    ├── test_session.py
    ├── test_web_search.py
    ├── test_observability.py
    └── test_integration.py      # End-to-end test case from section 6
```

## 11. Key Design Decisions

### 11.1 Why wrap Pydantic AI instead of using it directly?

Pydantic AI's native API requires manual agent construction, tool registration, and usage tracking for delegation. The workbench adds:
- **Declarative definitions** (`AgentDefinition`) that separate config from code
- **Registry-based discovery** that enables dynamic agent/tool lookup
- **Auto-injected delegation tools** that eliminate boilerplate delegation code
- **One-call observability setup** (`configure()`)

### 11.2 Why in-memory sessions for MVP?

SQLite adds a persistence layer (models, migrations, async driver, serialization). For MVP, the value is in validating the multi-agent loop, not session recovery. The `SessionManager` API is designed so SQLite can replace in-memory without breaking callers.

### 11.3 Why DuckDuckGo for web search?

No API key required. Zero configuration. Sufficient result quality for MVP. Can be swapped for a paid search API (Tavily, SerpAPI) in Phase 1.5 by registering a different function under the same `"web_search"` name.

### 11.4 Why sequential delegation instead of parallel subagents?

Parallel subagent execution requires an orchestrator-worker pattern with task decomposition, parallel task spawning, result collection, and synthesis. That's Phase 2 scope. Sequential delegation (parent calls one child via tool) is the simplest pattern that proves the multi-agent architecture works.

### 11.5 Why `subagents` on AgentDefinition instead of a separate workflow config?

For the MVP, delegation is the only pattern, and it's configured per-agent. A separate `Workflow` class would add indirection without value. When Phase 2 adds orchestrator-worker and handoff patterns, a `WorkflowPattern` base class will be introduced, and `AgentDefinition.subagents` will feed into it.

## 12. Out of Scope (Explicit)

The following are explicitly excluded from this MVP spec and will be addressed in future phases:

- **SQLite persistence** - Session/message storage to database (Phase 1.5)
- **Orchestrator-worker pattern** - Parallel subagent spawning and synthesis (Phase 2)
- **Programmatic handoff** - Sequential agent switching with message_history transfer (Phase 2)
- **Graph-based state machine** - Pydantic Graph integration (Phase 3)
- **HITL** - Pause/resume, approval workflows (Phase 3)
- **CLI** - Command-line interface (Phase 4)
- **FastAPI backend** - REST API (Phase 4)
- **Web UI** - Visual workflow designer and trace viewer (Phase 5)
- **Context management** - ProcessHistory, message compaction, summarization (Phase 1.5)
- **Error recovery** - Checkpoint, resume, rollback (Phase 3)
- **Multiple built-in tools** - Only web_search in MVP; http_request, write_file, code_exec in Phase 1.5
- **Agent routing** - Automatic agent selection based on query intent (Phase 2)
- **Durable execution** - Temporal integration (Phase 3+)
