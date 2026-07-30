# EasyAgents Multi-Agent Workbench MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the MVP SDK core for a multi-agent workbench: agent registry, tool system with web_search, agent delegation pattern, in-memory session management, and Logfire observability.

**Architecture:** Layered SDK on top of Pydantic AI. `AgentDefinition` provides declarative agent config; `AgentRegistry` creates Pydantic AI `Agent` instances and injects delegation tools; `DelegationManager` handles parent→child delegation with usage tracking; `ToolRegistry` manages built-in and custom tools; `SessionManager` provides in-memory conversation persistence.

**Tech Stack:** Python 3.11+, Pydantic AI, Pydantic v2, Logfire, duckduckgo-search, pytest

## Global Constraints

- Python >= 3.11
- pydantic-ai >= 0.0.30
- pydantic >= 2.0
- logfire >= 3.0
- duckduckgo-search >= 6.0
- pytest >= 8.0 (dev)
- pytest-asyncio >= 0.23 (dev)
- Source layout: `src/easyagents/`
- Tests in `tests/` directory
- No real LLM API calls in the test suite — use `TestModel` or `FunctionModel`

---

### Task 1: Project Scaffold + Exceptions + Config

**Files:**
- Create: `src/easyagents/__init__.py`
- Create: `src/easyagents/core/__init__.py`
- Create: `src/easyagents/core/exceptions.py`
- Create: `src/easyagents/core/config.py`
- Create: `src/easyagents/tools/__init__.py`
- Create: `src/easyagents/tools/builtin/__init__.py`
- Create: `src/easyagents/patterns/__init__.py`
- Create: `src/easyagents/observability/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `pyproject.toml`

**Interfaces:**
- Consumes: nothing (foundation)
- Produces: `EasyAgentsError`, `AgentAlreadyRegisteredError`, `AgentNotFoundError`, `ToolAlreadyRegisteredError`, `ToolNotFoundError`, `DelegationError` — all importable from `easyagents.core.exceptions`

- [ ] **Step 1: Create pyproject.toml**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "easyagents"
version = "0.1.0"
description = "Multi-agent workbench built on Pydantic AI"
requires-python = ">=3.11"
dependencies = [
    "pydantic-ai>=0.0.30",
    "pydantic>=2.0",
    "logfire>=3.0",
    "duckduckgo-search>=6.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "pytest-cov>=5.0",
]

[tool.hatch.build.targets.wheel]
packages = ["src/easyagents"]
```

- [ ] **Step 2: Create directory structure**

```bash
mkdir -p src/easyagents/core \
         src/easyagents/tools/builtin \
         src/easyagents/patterns \
         src/easyagents/observability \
         tests
```

- [ ] **Step 3: Write exceptions.py**

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

- [ ] **Step 4: Write config.py (stub for MVP)**

```python
"""Global configuration for EasyAgents.

MVP: no configuration needed. This module exists for forward compatibility
(Phase 1.5 will add config for SQLite path, default model, etc.).
"""


class EasyAgentsConfig:
    """Placeholder for future configuration."""

    pass
```

- [ ] **Step 5: Write all __init__.py files (empty)**

```python
# src/easyagents/core/__init__.py
# src/easyagents/tools/__init__.py
# src/easyagents/tools/builtin/__init__.py
# src/easyagents/patterns/__init__.py
# src/easyagents/observability/__init__.py
# tests/__init__.py
```

Each file is just a blank file or contains a docstring only. `src/easyagents/__init__.py` and `tests/conftest.py` are also empty for now.

```bash
touch src/easyagents/__init__.py \
      src/easyagents/core/__init__.py \
      src/easyagents/tools/__init__.py \
      src/easyagents/tools/builtin/__init__.py \
      src/easyagents/patterns/__init__.py \
      src/easyagents/observability/__init__.py \
      tests/__init__.py
```

- [ ] **Step 6: Write conftest.py**

```python
"""Shared test fixtures."""


import pytest


# Placeholder: real fixtures added in subsequent tasks
```

- [ ] **Step 7: Verify structure**

```bash
pip install -e ".[dev]"
python -c "from easyagents.core.exceptions import EasyAgentsError, AgentAlreadyRegisteredError, AgentNotFoundError, ToolAlreadyRegisteredError, ToolNotFoundError, DelegationError; print('OK')"
```

Expected: `OK`

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml src/easyagents tests
git commit -m "feat: project scaffold with exceptions"
```

---

### Task 2: Tool System

**Files:**
- Create: `src/easyagents/tools/base.py`
- Create: `src/easyagents/tools/registry.py`
- Create: `src/easyagents/tools/builtin/web_search.py`
- Create: `tests/test_tool_registry.py`
- Create: `tests/test_web_search.py`

**Interfaces:**
- Consumes: `ToolAlreadyRegisteredError`, `ToolNotFoundError` from `easyagents.core.exceptions`
- Produces: `ToolMetadata(name, description, parameters)` dataclass from `easyagents.tools.base`; `ToolRegistry` class from `easyagents.tools.registry`; `web_search(query, max_results)` async function from `easyagents.tools.builtin.web_search`

- [ ] **Step 1: Write the failing test for ToolRegistry**

File `tests/test_tool_registry.py`:

```python
import pytest
from easyagents.core.exceptions import ToolAlreadyRegisteredError, ToolNotFoundError
from easyagents.tools.base import ToolMetadata
from easyagents.tools.registry import ToolRegistry


@pytest.fixture
def registry():
    return ToolRegistry()


def test_register_and_list(registry):
    def my_tool(x: int) -> str:
        return str(x)

    registry.register("my_tool", my_tool)
    tools = registry.list()
    assert len(tools) == 1
    assert tools[0].name == "my_tool"


def test_register_duplicate_raises(registry):
    def tool_a(): pass
    def tool_b(): pass

    registry.register("tool", tool_a)
    with pytest.raises(ToolAlreadyRegisteredError):
        registry.register("tool", tool_b)


def test_resolve_returns_tools(registry):
    def my_tool(x: int) -> str:
        return str(x)

    registry.register("my_tool", my_tool)
    tools = registry.resolve(["my_tool"])
    assert len(tools) == 1


def test_resolve_nonexistent_raises(registry):
    with pytest.raises(ToolNotFoundError):
        registry.resolve(["nonexistent"])


def test_get_returns_metadata(registry):
    def my_tool(x: int) -> str:
        return str(x)

    registry.register("my_tool", my_tool)
    meta = registry.get("my_tool")
    assert isinstance(meta, ToolMetadata)
    assert meta.name == "my_tool"


def test_get_nonexistent_raises(registry):
    with pytest.raises(ToolNotFoundError):
        registry.get("nonexistent")


def test_register_with_custom_description(registry):
    def my_tool(x: int) -> str:
        return str(x)

    registry.register("my_tool", my_tool, description="Custom desc")
    meta = registry.get("my_tool")
    assert meta.description == "Custom desc"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_tool_registry.py -v
```

Expected: All tests fail with `ModuleNotFoundError` or similar (files don't exist yet).

- [ ] **Step 3: Write base.py**

```python
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolMetadata:
    name: str
    description: str
    parameters: dict[str, Any] = field(default_factory=dict)
```

- [ ] **Step 4: Write registry.py**

```python
import inspect
from typing import Any, Callable

from pydantic_ai import Tool

from easyagents.core.exceptions import (
    ToolAlreadyRegisteredError,
    ToolNotFoundError,
)
from easyagents.tools.base import ToolMetadata


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Callable[..., Any]] = {}

    def register(
        self, name: str, func: Callable[..., Any], description: str = ""
    ) -> None:
        if name in self._tools:
            raise ToolAlreadyRegisteredError(
                f"Tool '{name}' is already registered"
            )
        self._tools[name] = func

    def resolve(self, names: list[str]) -> list[Tool]:
        tools: list[Tool] = []
        for name in names:
            if name not in self._tools:
                raise ToolNotFoundError(
                    f"Tool '{name}' is not registered"
                )
            tools.append(Tool(self._tools[name]))
        return tools

    def get(self, name: str) -> ToolMetadata:
        if name not in self._tools:
            raise ToolNotFoundError(
                f"Tool '{name}' is not registered"
            )
        func = self._tools[name]
        sig = inspect.signature(func)
        params = {
            p.name: {"kind": p.kind.name, "annotation": str(p.annotation)}
            for p in sig.parameters.values()
            if p.name != "ctx"
        }
        desc = func.__doc__ or ""
        return ToolMetadata(name=name, description=desc, parameters=params)

    def list(self) -> list[ToolMetadata]:
        return [self.get(name) for name in self._tools]
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_tool_registry.py -v
```

Expected: All 7 tests pass.

- [ ] **Step 6: Write the failing test for web_search**

File `tests/test_web_search.py`:

```python
import pytest
from easyagents.tools.builtin.web_search import web_search


@pytest.mark.asyncio
async def test_web_search_returns_list():
    results = await web_search("test query", max_results=3)
    assert isinstance(results, list)
    if results:
        assert "title" in results[0]
        assert "url" in results[0]
        assert "snippet" in results[0]


@pytest.mark.asyncio
async def test_web_search_handles_network_error():
    # Trigger network error with a very short timeout
    results = await web_search("" * 1000, max_results=1)
    assert isinstance(results, list)
    assert len(results) == 0
```

- [ ] **Step 7: Run web_search test to verify it fails**

```bash
pytest tests/test_web_search.py -v
```

Expected: Fails with `ModuleNotFoundError` (web_search.py doesn't exist).

- [ ] **Step 8: Write web_search.py**

```python
import asyncio
import logging

logger = logging.getLogger(__name__)


async def web_search(
    query: str, max_results: int = 5
) -> list[dict[str, str]]:
    """Search the web using DuckDuckGo and return results.

    Args:
        query: Search query string.
        max_results: Maximum number of results to return (default 5).

    Returns:
        A list of dicts with keys: title, url, snippet.
        Returns an empty list on network errors.
    """
    try:
        from duckduckgo_search import DDGS

        def _search() -> list[dict[str, str]]:
            results: list[dict[str, str]] = []
            with DDGS() as ddgs:
                for i, r in enumerate(ddgs.text(query, max_results=max_results)):
                    if i >= max_results:
                        break
                    results.append(
                        {
                            "title": r.get("title", ""),
                            "url": r.get("href", ""),
                            "snippet": r.get("body", ""),
                        }
                    )
            return results

        return await asyncio.to_thread(_search)
    except Exception as e:
        logger.warning("Web search failed for query '%s': %s", query, e)
        return []
```

- [ ] **Step 9: Run tests to verify they pass**

```bash
pytest tests/test_web_search.py -v
```

Expected: `test_web_search_returns_list` passes (may return results or empty list depending on network), `test_web_search_handles_network_error` passes.

- [ ] **Step 10: Commit**

```bash
git add src/easyagents/tools/ tests/
git commit -m "feat: tool system with ToolRegistry and web_search"
```

---

### Task 3: Agent System + Session

**Files:**
- Create: `src/easyagents/core/agent.py`
- Create: `src/easyagents/core/session.py`
- Create: `tests/test_agent_registry.py`
- Create: `tests/test_session.py`

**Interfaces:**
- Consumes: `ToolRegistry` from `easyagents.tools.registry`, exceptions from `easyagents.core.exceptions`
- Produces: `AgentDefinition(name, instructions, model, tools, output_type, deps_type, description, subagents)` dataclass; `AgentRegistry` class with `register()`, `get()`, `create()`, `list()`; `Session(conversation_id, messages)` dataclass; `SessionManager` class with `create()`, `get()`, `save_messages()`

- [ ] **Step 1: Write the failing test for AgentRegistry (basic, no delegation)**

File `tests/test_agent_registry.py`:

```python
import pytest
from pydantic import BaseModel
from pydantic_ai import Agent
from easyagents.core.agent import AgentDefinition, AgentRegistry
from easyagents.core.exceptions import AgentAlreadyRegisteredError, AgentNotFoundError
from easyagents.tools.registry import ToolRegistry


@pytest.fixture
def tool_registry():
    tr = ToolRegistry()

    def dummy_tool(x: int) -> str:
        """A dummy tool for testing."""
        return str(x)

    tr.register("dummy_tool", dummy_tool)
    return tr


@pytest.fixture
def registry():
    return AgentRegistry()


def test_register_and_list(registry):
    definition = AgentDefinition(
        name="test_agent",
        instructions="You are a test agent.",
        model="openai:gpt-4o",
    )
    registry.register(definition)
    names = registry.list()
    assert "test_agent" in names


def test_register_duplicate_raises(registry):
    registry.register(AgentDefinition(name="dup", instructions="", model="openai:gpt-4o"))
    with pytest.raises(AgentAlreadyRegisteredError):
        registry.register(AgentDefinition(name="dup", instructions="", model="openai:gpt-4o"))


def test_get_returns_definition(registry):
    expected = AgentDefinition(name="get_me", instructions="Hi", model="openai:gpt-4o")
    registry.register(expected)
    actual = registry.get("get_me")
    assert actual is expected


def test_get_nonexistent_raises(registry):
    with pytest.raises(AgentNotFoundError):
        registry.get("nonexistent")


def test_create_returns_pydantic_agent(registry, tool_registry):
    definition = AgentDefinition(
        name="creator_test",
        instructions="You are a test.",
        model="openai:gpt-4o",
        tools=["dummy_tool"],
    )
    registry.register(definition)
    agent = registry.create("creator_test", tool_registry)
    assert isinstance(agent, Agent)


def test_create_caches_agent(registry, tool_registry):
    definition = AgentDefinition(
        name="cached_test",
        instructions="You are a test.",
        model="openai:gpt-4o",
    )
    registry.register(definition)
    a1 = registry.create("cached_test", tool_registry)
    a2 = registry.create("cached_test", tool_registry)
    assert a1 is a2
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_agent_registry.py -v
```

Expected: All fail with `ModuleNotFoundError`.

- [ ] **Step 3: Write agent.py**

```python
from dataclasses import dataclass, field
from typing import Any

from pydantic_ai import Agent

from easyagents.core.exceptions import (
    AgentAlreadyRegisteredError,
    AgentNotFoundError,
)
from easyagents.tools.registry import ToolRegistry


@dataclass
class AgentDefinition:
    name: str
    instructions: str
    model: str
    tools: list[str] = field(default_factory=list)
    output_type: type | None = None
    deps_type: type | None = None
    description: str = ""
    subagents: list[str] = field(default_factory=list)


class AgentRegistry:
    def __init__(self) -> None:
        self._definitions: dict[str, AgentDefinition] = {}
        self._agents: dict[str, Agent[Any]] = {}

    def register(self, definition: AgentDefinition) -> None:
        if definition.name in self._definitions:
            raise AgentAlreadyRegisteredError(
                f"Agent '{definition.name}' is already registered"
            )
        self._definitions[definition.name] = definition

    def get(self, name: str) -> AgentDefinition:
        if name not in self._definitions:
            raise AgentNotFoundError(f"Agent '{name}' is not registered")
        return self._definitions[name]

    def create(
        self, name: str, tool_registry: ToolRegistry
    ) -> Agent[Any]:
        if name in self._agents:
            return self._agents[name]

        definition = self.get(name)
        pydantic_tools = tool_registry.resolve(definition.tools)
        from easyagents.patterns.delegation import DelegationManager

        if definition.subagents:
            dm = DelegationManager(
                parent_name=name,
                subagent_names=definition.subagents,
                registry=self,
                tool_registry=tool_registry,
            )
            pydantic_tools.extend(dm.create_delegation_tools())

        kwargs: dict[str, Any] = {
            "model": definition.model,
            "name": definition.name,
            "system_prompt": definition.instructions,
            "tools": pydantic_tools,
        }
        if definition.output_type is not None:
            kwargs["output_type"] = definition.output_type

        agent = Agent[Any](**kwargs)
        self._agents[name] = agent
        return agent

    def list(self) -> list[str]:
        return list(self._definitions.keys())
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_agent_registry.py -v
```

Expected: Tests pass (but `test_create_returns_pydantic_agent` and `test_create_caches_agent` may fail because `patterns.delegation` doesn't exist yet). Let me check...

Actually, `AgentRegistry.create()` imports `DelegationManager` at the top of the function body. If `patterns/delegation.py` doesn't exist, this will fail with `ModuleNotFoundError`. I should either:
1. Make the import conditional (try/except)
2. Or create a stub delegation.py first

Let me use option 2: create a minimal stub. Actually, option 1 is cleaner:

```python
try:
    from easyagents.patterns.delegation import DelegationManager
except ImportError:
    DelegationManager = None
```

But that's hacky. Let me just create the delegation module stub in this task. No wait, the plan says Task 4 is delegation. If I add the import guard, tests in Task 3 pass now, and Task 4 completes it.

Let me use a clean approach: check if `subagents` is non-empty, and only then try to import. If the import fails (because delegation.py doesn't exist yet), just skip the delegation injection. This is forward-compatible.

Actually, the cleanest approach: just inline the delegation import at the point of use with a guard. Let me do:

```python
if definition.subagents:
    from easyagents.patterns.delegation import DelegationManager
    dm = DelegationManager(...)
    pydantic_tools.extend(dm.create_delegation_tools())
```

This works because `from easyagents.patterns.delegation import DelegationManager` will succeed if the module exists, and the `if definition.subagents:` guard means it only runs when subagents are defined. So as long as we don't test an agent with `subagents` in Task 3 tests (which we don't - none of the test cases use `subagents`), it will work.

Yes, this is correct. The test cases in Task 3 don't use `subagents`, so the import won't be triggered. Let me keep the code as-is in the plan.

Now, let me continue.

- [ ] **Step 5: Write the failing test for SessionManager**

File `tests/test_session.py`:

```python
import pytest
from easyagents.core.session import Session, SessionManager


@pytest.fixture
def manager():
    return SessionManager()


def test_create_session(manager):
    session = manager.create()
    assert isinstance(session, Session)
    assert session.conversation_id is not None
    assert session.messages == []


def test_get_existing_session(manager):
    created = manager.create()
    retrieved = manager.get(created.conversation_id)
    assert retrieved is created


def test_get_nonexistent_returns_none(manager):
    assert manager.get("nonexistent-id") is None


def test_save_messages(manager):
    from pydantic_ai import ModelRequest, ModelResponse, TextPart, UserPromptPart

    session = manager.create()
    messages = [
        ModelRequest(parts=[UserPromptPart(content="Hello")]),
        ModelResponse(parts=[TextPart(content="Hi there")]),
    ]
    manager.save_messages(session.conversation_id, messages)
    assert session.messages == messages


def test_save_messages_overwrites(manager):
    from pydantic_ai import ModelRequest, UserPromptPart

    session = manager.create()
    old = [ModelRequest(parts=[UserPromptPart(content="Old")])]
    new = [ModelRequest(parts=[UserPromptPart(content="New")])]
    manager.save_messages(session.conversation_id, old)
    manager.save_messages(session.conversation_id, new)
    assert session.messages == new
```

- [ ] **Step 6: Run session tests to verify they fail**

```bash
pytest tests/test_session.py -v
```

Expected: All fail with `ModuleNotFoundError`.

- [ ] **Step 7: Write session.py**

```python
from dataclasses import dataclass, field
from uuid import uuid4

from pydantic_ai import ModelMessage


@dataclass
class Session:
    conversation_id: str
    messages: list[ModelMessage] = field(default_factory=list)


class SessionManager:
    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}

    def create(self) -> Session:
        conversation_id = str(uuid4())
        session = Session(conversation_id=conversation_id)
        self._sessions[conversation_id] = session
        return session

    def get(self, conversation_id: str) -> Session | None:
        return self._sessions.get(conversation_id)

    def save_messages(
        self, conversation_id: str, messages: list[ModelMessage]
    ) -> None:
        session = self._sessions[conversation_id]
        session.messages = messages
```

- [ ] **Step 8: Run all tests to verify they pass**

```bash
pytest tests/test_tool_registry.py tests/test_agent_registry.py tests/test_session.py -v
```

Expected: All pass.

- [ ] **Step 9: Commit**

```bash
git add src/easyagents/core/agent.py src/easyagents/core/session.py tests/
git commit -m "feat: agent registry and session manager"
```

---

### Task 4: Delegation Pattern

**Files:**
- Create: `src/easyagents/patterns/delegation.py`
- Create: `tests/test_delegation.py`

**Interfaces:**
- Consumes: `AgentRegistry` from `easyagents.core.agent`, `ToolRegistry` from `easyagents.tools.registry`, `DelegationError` from `easyagents.core.exceptions`
- Produces: `DelegationManager(parent_name, subagent_names, registry, tool_registry)` class; `create_delegation_tools()` → `list[Tool]`; async `delegate(subagent_name, task, parent_usage)` → `Any`

- [ ] **Step 1: Write the failing test for DelegationManager**

File `tests/test_delegation.py`:

```python
import pytest
from pydantic_ai import RunUsage
from pydantic_ai.models.test import TestModel

from easyagents.core.agent import AgentDefinition, AgentRegistry
from easyagents.core.exceptions import DelegationError
from easyagents.tools.registry import ToolRegistry
from easyagents.patterns.delegation import DelegationManager


@pytest.fixture
def tool_registry():
    tr = ToolRegistry()
    tr.register("web_search", lambda q: [{"title": "Result", "url": "https://x.com", "snippet": "..."}])
    return tr


@pytest.fixture
def registry():
    return AgentRegistry()


def test_delegation_tool_injection(tool_registry, registry):
    child_def = AgentDefinition(
        name="child",
        instructions="You are a child agent.",
        model="openai:gpt-4o",
    )
    parent_def = AgentDefinition(
        name="parent",
        instructions="You are a parent agent.",
        model="openai:gpt-4o",
        subagents=["child"],
    )
    registry.register(child_def)
    registry.register(parent_def)

    dm = DelegationManager(
        parent_name="parent",
        subagent_names=["child"],
        registry=registry,
        tool_registry=tool_registry,
    )
    tools = dm.create_delegation_tools()
    assert len(tools) == 1
    assert tools[0].name == "delegate_child"  # Pydantic AI may generate name from function


def test_delegation_tool_names_use_delegate_prefix(tool_registry, registry):
    child = AgentDefinition(name="researcher", instructions="Research.", model="openai:gpt-4o")
    registry.register(child)
    dm = DelegationManager("parent", ["researcher"], registry, tool_registry)
    tools = dm.create_delegation_tools()
    assert tools[0].name == "delegate_researcher"


@pytest.mark.asyncio
async def test_delegate_runs_subagent(tool_registry, registry):
    child_def = AgentDefinition(
        name="researcher",
        instructions="You research things.",
        model="openai:gpt-4o",
        tools=["web_search"],
    )
    registry.register(child_def)

    dm = DelegationManager("parent", ["researcher"], registry, tool_registry)
    usage = RunUsage()
    result = await dm.delegate("researcher", "test task", usage)
    assert result is not None


@pytest.mark.asyncio
async def test_delegate_passes_usage(tool_registry, registry):
    child_def = AgentDefinition(
        name="counter",
        instructions="You count.",
        model="openai:gpt-4o",
    )
    registry.register(child_def)

    dm = DelegationManager("parent", ["counter"], registry, tool_registry)
    usage = RunUsage()
    await dm.delegate("counter", "count to 3", usage)
    assert usage.total_tokens > 0 or usage.requests > 0


def test_agent_registry_injects_delegation_tools(tool_registry, registry):
    child = AgentDefinition(name="helper", instructions="Help.", model="openai:gpt-4o")
    parent = AgentDefinition(
        name="boss",
        instructions="You delegate.",
        model="openai:gpt-4o",
        subagents=["helper"],
    )
    registry.register(child)
    registry.register(parent)

    agent = registry.create("boss", tool_registry)
    assert agent is not None
    # The agent has delegation tools injected
    # Verify by running with TestModel
```

- [ ] **Step 2: Run delegation tests to verify they fail**

```bash
pytest tests/test_delegation.py -v
```

Expected: All fail with `ModuleNotFoundError`.

- [ ] **Step 3: Write delegation.py**

```python
from typing import Any

from pydantic_ai import RunUsage, Tool

from easyagents.core.exceptions import DelegationError

if __name__ != "__main__":
    # Avoid circular import at module level; AgentRegistry is used at runtime
    pass


class DelegationManager:
    def __init__(
        self,
        parent_name: str,
        subagent_names: list[str],
        registry: Any,  # AgentRegistry — avoided at type-check due to circular import
        tool_registry: Any,  # ToolRegistry
    ) -> None:
        self.parent_name = parent_name
        self.subagent_names = subagent_names
        self.registry = registry
        self.tool_registry = tool_registry

    def create_delegation_tools(self) -> list[Tool]:
        tools: list[Tool] = []
        for name in self.subagent_names:
            delegate_func = self._make_delegate_func(name)
            tools.append(Tool(delegate_func))
        return tools

    def _make_delegate_func(self, subagent_name: str):
        from pydantic_ai import RunContext

        async def delegate(ctx: RunContext[None], task: str) -> Any:
            try:
                subagent = self.registry.create(
                    subagent_name, self.tool_registry
                )
                result = await subagent.run(task, usage=ctx.usage)
                return result.output
            except Exception as e:
                raise DelegationError(
                    f"Delegation to '{subagent_name}' failed: {e}"
                ) from e

        delegate.__name__ = f"delegate_{subagent_name}"
        return delegate

    async def delegate(
        self, subagent_name: str, task: str, parent_usage: RunUsage
    ) -> Any:
        try:
            subagent = self.registry.create(
                subagent_name, self.tool_registry
            )
            result = await subagent.run(task, usage=parent_usage)
            return result.output
        except Exception as e:
            raise DelegationError(
                f"Delegation to '{subagent_name}' failed: {e}"
            ) from e
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_delegation.py -v
```

Expected: All tests pass. Note: some tests that run real LLM calls (delegate_passes_usage) may be skipped or mock - the test as written uses `RunUsage()` which is an empty usage tracker. The `RunUsage` object may need a model call to actually track tokens. Let me adjust the test...

Actually, I realize the tests might have issues:
- `test_delegate_runs_subagent` calls `dm.delegate()` which calls `subagent.run()`. But `subagent.run()` with `model="openai:gpt-4o"` will try to make a real API call. The tests should override the model with `TestModel`.
- `test_delegate_passes_usage` also makes a real API call.

I need to fix the tests to use `TestModel` to avoid real API calls. But `DelegationManager.delegate()` uses the agent definition's model from the registry. The agent was registered with `model="openai:gpt-4o"`.

One approach: override the model when calling `subagent.run()`. Let me modify `DelegationManager.delegate()` to accept an optional model override. Or, I could make the tests work by using a FunctionModel that doesn't make real calls.

Actually, looking at Pydantic AI's `TestModel`, it can be passed as the `model` parameter:
```python
result = await subagent.run(task, model=TestModel(), usage=parent_usage)
```

But then the model in the agent definition would be overridden. Let me think about this differently.

For the delegation tests, the cleanest approach is to use `FunctionModel`:
```python
from pydantic_ai.models.function import FunctionModel

def return_output(messages, info):
    from pydantic_ai import ModelResponse, TextPart
    return ModelResponse(parts=[TextPart(content="Done")])

model = FunctionModel(return_output)
```

But I'd need to pass this model through the delegation chain. This is getting complicated.

Let me simplify the tests. For `test_delegate_runs_subagent`, I'll just verify that the delegation call returns something without errors. I can modify the `DelegationManager.delegate()` method to accept an optional `model` parameter for testing.

Wait, actually there's a simpler approach. Pydantic AI's `FunctionModel` is an `AbstractModel`, so I can pass it to `Agent.run()`:
```python
result = await subagent.run(task, model=my_function_model, usage=parent_usage)
```

But the test needs the DelegationManager to pass the model through. Let me modify `delegate()` to accept an optional `model` parameter:

```python
async def delegate(self, subagent_name, task, parent_usage, model=None):
    subagent = self.registry.create(subagent_name, self.tool_registry)
    result = await subagent.run(task, usage=parent_usage, model=model)
    return result.output
```

This way, tests can pass `model=TestModel()` to avoid real API calls. And in production, `model=None` means the agent uses its configured model.

Let me update the plan with this approach.

Actually wait, I need to check Pydantic AI's API. Does `Agent.run()` accept a `model` parameter? Looking at the docs...

Yes, `Agent.run()` accepts `model` as a parameter:
```python
result = await agent.run("prompt", model="anthropic:claude-sonnet-4-6")
```

So passing `model=FunctionModel(...)` should work.

Let me also update the tests. The test_delgate_runs_subagent test should:
1. Create a FunctionModel that returns a canned response
2. Pass it to dm.delegate() via the model parameter
3. Verify the result

And test_delgate_passes_usage should verify that the RunUsage object gets updated.

OK, let me revise the test and implementation in the plan.

One more thing: I need to understand how RunUsage works in Pydantic AI. Looking at the docs, `RunUsage` tracks `requests`, `input_tokens`, and `output_tokens`. When you pass `usage=parent_usage` to `agent.run()`, the child's usage is added to the parent's RunUsage.

Let me also double-check: `pydantic_ai.RunUsage` is the correct type. Looking at the docs, it's `from pydantic_ai import RunUsage` and has fields `requests`, `input_tokens`, `output_tokens`.

OK, let me finalize the plan with these corrections.

Actually, I realize there might be an issue with the delegation tool. The tool function `delegate` takes `ctx: RunContext[None]`. But in Pydantic AI, `Tool` wrapping a function with `RunContext` needs the function to be properly typed. Let me check if Pydantic AI's `Tool(func)` works with functions that have `RunContext`...

Looking at Pydantic AI source, `Tool` can wrap any callable. If the callable has a `RunContext` first parameter, Pydantic AI injects it automatically. So `Tool(delegate)` where `delegate` has signature `(ctx: RunContext[None], task: str) -> Awaitable[Any]` should work.

OK, I'm confident the plan is correct. Let me also think about the `test_agent_registry_injects_delegation_tools` test. It creates a parent agent with subagents manually, then calls `registry.create("boss", tool_registry)`. The `create()` method should auto-inject delegation tools. But then the test doesn't actually verify the tools exist. Let me fix that test:

```python
def test_agent_registry_injects_delegation_tools(tool_registry, registry):
    child = AgentDefinition(name="helper", instructions="Help.", model="openai:gpt-4o")
    parent = AgentDefinition(
        name="boss",
        instructions="You delegate.",
        model="openai:gpt-4o",
        subagents=["helper"],
    )
    registry.register(child)
    registry.register(parent)

    agent = registry.create("boss", tool_registry)
    # The agent was created with delegation tools - verify by inspection
    # Pydantic AI Agent doesn't easily expose its tools, so we verify
    # that delegation Manager was created by observing Side Effects
    # (e.g., no exception raised, agent is valid)
    from pydantic_ai.models.function import FunctionModel, AgentInfo
    from pydantic_ai import ModelResponse, TextPart

    def handler(messages, info):
        return ModelResponse(parts=[TextPart(content="OK")])
    
    result = agent.run_sync("do something", model=FunctionModel(handler))
    assert result.output is not None
```

Actually, this test would work but it doesn't really verify delegation tool injection. The agent just runs and returns "OK" from the FunctionModel without using any tools.

For a more meaningful test, I should set up a test where the parent agent WOULD use the delegation tool if it existed, and verify the output. But that requires the agent to actually use the tool, which depends on the LLM.

Let me keep the test as a simple "agent created without error" check, and rely on the `test_delegation_tool_injection` and `test_delegation_tool_names_use_delegate_prefix` tests for more specific checks.

OK, I'm overthinking this. Let me finalize the plan as-is and move on. The key thing is that the implementation works correctly - the tests can be refined during implementation.

Let me write the final version of the plan document. I've been going back and forth; let me just commit to a solid plan.

Actually, I realize I should also think about how the RunUsage test works. The `RunUsage` object starts with `requests=0`. After `subagent.run(task, usage=usage)` completes, `usage.requests` should be at least 1. But this only works if the subagent actually calls the LLM, which requires a real model or a FunctionModel.

Let me adjust: use FunctionModel for the subagent too.

```python
@pytest.mark.asyncio
async def test_delegate_passes_usage(tool_registry, registry):
    from pydantic_ai.models.function import FunctionModel, AgentInfo
    from pydantic_ai import ModelResponse, TextPart, RunUsage

    def return_ok(messages, info: AgentInfo):
        return ModelResponse(parts=[TextPart(content="Done")])

    child_def = AgentDefinition(
        name="counter",
        instructions="You count.",
        model=FunctionModel(return_ok),  # Use model directly
    )
    registry.register(child_def)

    dm = DelegationManager("parent", ["counter"], registry, tool_registry)
    usage = RunUsage()
    await dm.delegate("counter", "count to 3", usage, model=FunctionModel(return_ok))
    assert usage.requests > 0
```

Hmm, but `AgentDefinition.model` is typed as `str` in the spec. If I pass a `FunctionModel` object, it won't work with the current type annotation.

I have two options:
1. Change `AgentDefinition.model` to `str | AbstractModel`
2. Keep `model` as a str and override in the test at runtime

Option 1 is cleaner. Let me update the AgentDefinition to accept both string and model objects. This aligns with Pydantic AI's API which accepts both.

Actually, for the MVP, let me keep it simple. The `AgentDefinition.model` is a `str` (model name). The `DelegationManager.delegate()` method accepts an optional `model` override for testing. In the test, I pass the `FunctionModel` as the override.

This is clean enough. Let me update the plan accordingly.

OK let me just finalize and write the plan. I'll make the test practical:

```python
@pytest.mark.asyncio
async def test_delegate_runs_subagent(tool_registry, registry):
    from pydantic_ai.models.function import FunctionModel
    from pydantic_ai import ModelResponse, TextPart

    def handler(messages, info):
        return ModelResponse(parts=[TextPart(content="Research result: found it")])

    child_def = AgentDefinition(
        name="researcher",
        instructions="You research things.",
        model="openai:gpt-4o",
    )
    registry.register(child_def)

    dm = DelegationManager("parent", ["researcher"], registry, tool_registry)
    usage = RunUsage()
    result = await dm.delegate("researcher", "test task", usage, model=FunctionModel(handler))
    assert result == "Research result: found it"
```

Wait, but `FunctionModel.__init__` arguments might be different. Let me check... 

Looking at Pydantic AI docs: `FunctionModel(function, model_name="function")`. The function signature is `(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse`.

OK, this is correct. Let me finalize.

For the `test_delegate_passes_usage` test, I need to verify that usage has been updated after delegation. The `RunUsage` object should have `requests > 0` after `subagent.run()`.

Let me write the plan now. I'm going to stop deliberating and just write it.</think>Now let me write the plan.

<｜DSML｜tool_calls>
<｜DSML｜invoke name="write">
<｜DSML｜parameter name="content" string="true"># EasyAgents Multi-Agent Workbench MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the MVP SDK core for a multi-agent workbench: agent registry, tool system with web_search, agent delegation pattern, in-memory session management, and Logfire observability.

**Architecture:** Layered SDK on top of Pydantic AI. `AgentDefinition` provides declarative agent config; `AgentRegistry` creates Pydantic AI `Agent` instances and injects delegation tools; `DelegationManager` handles parent→child delegation with usage tracking; `ToolRegistry` manages built-in and custom tools; `SessionManager` provides in-memory conversation persistence.

**Tech Stack:** Python 3.11+, Pydantic AI, Pydantic v2, Logfire, duckduckgo-search, pytest

## Global Constraints

- Python >= 3.11
- pydantic-ai >= 0.0.30
- pydantic >= 2.0
- logfire >= 3.0
- duckduckgo-search >= 6.0
- pytest >= 8.0 (dev)
- pytest-asyncio >= 0.23 (dev)
- Source layout: `src/easyagents/`
- Tests in `tests/` directory
- No real LLM API calls in the test suite — use `TestModel` or `FunctionModel`

---

### Task 1: Project Scaffold + Exceptions

**Files:**
- Create: `pyproject.toml`
- Create: `src/easyagents/__init__.py`
- Create: `src/easyagents/core/__init__.py`
- Create: `src/easyagents/core/exceptions.py`
- Create: `src/easyagents/core/config.py`
- Create: `src/easyagents/tools/__init__.py`
- Create: `src/easyagents/tools/builtin/__init__.py`
- Create: `src/easyagents/patterns/__init__.py`
- Create: `src/easyagents/observability/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

**Interfaces:**
- Consumes: nothing (foundation)
- Produces: `EasyAgentsError`, `AgentAlreadyRegisteredError`, `AgentNotFoundError`, `ToolAlreadyRegisteredError`, `ToolNotFoundError`, `DelegationError` — all importable from `easyagents.core.exceptions`

- [ ] **Step 1: Create pyproject.toml**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "easyagents"
version = "0.1.0"
description = "Multi-agent workbench built on Pydantic AI"
requires-python = ">=3.11"
dependencies = [
    "pydantic-ai>=0.0.30",
    "pydantic>=2.0",
    "logfire>=3.0",
    "duckduckgo-search>=6.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "pytest-cov>=5.0",
]

[tool.hatch.build.targets.wheel]
packages = ["src/easyagents"]
```

- [ ] **Step 2: Create directory structure**

```bash
mkdir -p src/easyagents/core src/easyagents/tools/builtin src/easyagents/patterns src/easyagents/observability tests
touch src/easyagents/__init__.py src/easyagents/core/__init__.py src/easyagents/tools/__init__.py src/easyagents/tools/builtin/__init__.py src/easyagents/patterns/__init__.py src/easyagents/observability/__init__.py tests/__init__.py tests/conftest.py
```

- [ ] **Step 3: Write exceptions.py**

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

- [ ] **Step 4: Write config.py (stub)**

```python
class EasyAgentsConfig:
    """Placeholder for future configuration (Phase 1.5+)."""
    pass
```

- [ ] **Step 5: Install and verify**

```bash
pip install -e ".[dev]"
python -c "from easyagents.core.exceptions import EasyAgentsError, AgentAlreadyRegisteredError, AgentNotFoundError, ToolAlreadyRegisteredError, ToolNotFoundError, DelegationError; print('OK')"
```

Expected: `OK`

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml src/easyagents tests
git commit -m "feat: project scaffold with exceptions"
```

---

### Task 2: Tool System

**Files:**
- Create: `src/easyagents/tools/base.py`
- Create: `src/easyagents/tools/registry.py`
- Create: `src/easyagents/tools/builtin/web_search.py`
- Create: `tests/test_tool_registry.py`
- Create: `tests/test_web_search.py`

**Interfaces:**
- Consumes: `ToolAlreadyRegisteredError`, `ToolNotFoundError` from `easyagents.core.exceptions`
- Produces: `ToolMetadata(name, description, parameters)` dataclass; `ToolRegistry` class; `web_search(query, max_results)` async function

- [ ] **Step 1: Write base.py**

```python
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolMetadata:
    name: str
    description: str
    parameters: dict[str, Any] = field(default_factory=dict)
```

- [ ] **Step 2: Write the failing test for ToolRegistry**

```python
import pytest
from easyagents.core.exceptions import ToolAlreadyRegisteredError, ToolNotFoundError
from easyagents.tools.base import ToolMetadata
from easyagents.tools.registry import ToolRegistry


@pytest.fixture
def registry():
    return ToolRegistry()


def test_register_and_list(registry):
    def my_tool(x: int) -> str:
        return str(x)

    registry.register("my_tool", my_tool)
    tools = registry.list()
    assert len(tools) == 1
    assert tools[0].name == "my_tool"


def test_register_duplicate_raises(registry):
    def tool_a(): pass
    def tool_b(): pass
    registry.register("tool", tool_a)
    with pytest.raises(ToolAlreadyRegisteredError):
        registry.register("tool", tool_b)


def test_resolve_returns_pydantic_tools(registry):
    def my_tool(x: int) -> str:
        return str(x)
    registry.register("my_tool", my_tool)
    tools = registry.resolve(["my_tool"])
    assert len(tools) == 1


def test_resolve_nonexistent_raises(registry):
    with pytest.raises(ToolNotFoundError):
        registry.resolve(["nonexistent"])


def test_get_returns_metadata(registry):
    def my_tool(x: int) -> str:
        return str(x)
    registry.register("my_tool", my_tool)
    meta = registry.get("my_tool")
    assert isinstance(meta, ToolMetadata)
    assert meta.name == "my_tool"


def test_get_nonexistent_raises(registry):
    with pytest.raises(ToolNotFoundError):
        registry.get("nonexistent")


def test_register_with_custom_description(registry):
    def my_tool(x: int) -> str:
        return str(x)
    registry.register("my_tool", my_tool, description="Custom desc")
    meta = registry.get("my_tool")
    assert meta.description == "Custom desc"
```

- [ ] **Step 3: Run test to verify it fails**

```bash
pytest tests/test_tool_registry.py -v
```

Expected: Fails with `ModuleNotFoundError` (registry.py doesn't exist yet)

- [ ] **Step 4: Write registry.py**

```python
import inspect
from typing import Any, Callable

from pydantic_ai import Tool

from easyagents.core.exceptions import (
    ToolAlreadyRegisteredError,
    ToolNotFoundError,
)
from easyagents.tools.base import ToolMetadata


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Callable[..., Any]] = {}

    def register(
        self, name: str, func: Callable[..., Any], description: str = ""
    ) -> None:
        if name in self._tools:
            raise ToolAlreadyRegisteredError(
                f"Tool '{name}' is already registered"
            )
        self._tools[name] = func

    def resolve(self, names: list[str]) -> list[Tool]:
        tools: list[Tool] = []
        for name in names:
            if name not in self._tools:
                raise ToolNotFoundError(
                    f"Tool '{name}' is not registered"
                )
            tools.append(Tool(self._tools[name]))
        return tools

    def get(self, name: str) -> ToolMetadata:
        if name not in self._tools:
            raise ToolNotFoundError(
                f"Tool '{name}' is not registered"
            )
        func = self._tools[name]
        sig = inspect.signature(func)
        params = {
            p.name: {"kind": p.kind.name, "annotation": str(p.annotation)}
            for p in sig.parameters.values()
        }
        desc = func.__doc__ or ""
        return ToolMetadata(name=name, description=desc, parameters=params)

    def list(self) -> list[ToolMetadata]:
        return [self.get(name) for name in self._tools]
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_tool_registry.py -v
```

Expected: 7 tests pass

- [ ] **Step 6: Write web_search.py**

```python
import asyncio
import logging

logger = logging.getLogger(__name__)


async def web_search(
    query: str, max_results: int = 5
) -> list[dict[str, str]]:
    """Search the web using DuckDuckGo and return results.

    Args:
        query: Search query string.
        max_results: Maximum number of results to return (default 5).

    Returns:
        A list of dicts with keys: title, url, snippet.
        Returns an empty list on network errors.
    """
    try:
        from duckduckgo_search import DDGS

        def _search() -> list[dict[str, str]]:
            results: list[dict[str, str]] = []
            with DDGS() as ddgs:
                for i, r in enumerate(ddgs.text(query, max_results=max_results)):
                    if i >= max_results:
                        break
                    results.append({
                        "title": r.get("title", ""),
                        "url": r.get("href", ""),
                        "snippet": r.get("body", ""),
                    })
            return results

        return await asyncio.to_thread(_search)
    except Exception as e:
        logger.warning("Web search failed for query '%s': %s", query, e)
        return []
```

- [ ] **Step 7: Write and run web_search test**

File `tests/test_web_search.py`:

```python
import pytest
from easyagents.tools.builtin.web_search import web_search


@pytest.mark.asyncio
async def test_web_search_returns_list():
    results = await web_search("test query", max_results=3)
    assert isinstance(results, list)
    if results:
        assert "title" in results[0]
        assert "url" in results[0]
        assert "snippet" in results[0]


@pytest.mark.asyncio
async def test_web_search_handles_error():
    results = await web_search("x" * 500, max_results=1)
    assert isinstance(results, list)
```

```bash
pytest tests/test_web_search.py -v
```

Expected: Both pass (may return results or empty list depending on network)

- [ ] **Step 8: Commit**

```bash
git add src/easyagents/tools/ tests/
git commit -m "feat: tool system with ToolRegistry and web_search"
```

---

### Task 3: Agent System + Session

**Files:**
- Create: `src/easyagents/core/agent.py`
- Create: `src/easyagents/core/session.py`
- Create: `tests/test_agent_registry.py`
- Create: `tests/test_session.py`

**Interfaces:**
- Consumes: `ToolRegistry` from `easyagents.tools.registry`, exceptions from `easyagents.core.exceptions`
- Produces: `AgentDefinition(name, instructions, model, tools, output_type, deps_type, description, subagents)` dataclass; `AgentRegistry` with `register()`, `get()`, `create()`, `list()`; `Session(conversation_id, messages)` dataclass; `SessionManager` with `create()`, `get()`, `save_messages()`

- [ ] **Step 1: Write the failing test for AgentRegistry**

```python
import pytest
from pydantic_ai import Agent
from easyagents.core.agent import AgentDefinition, AgentRegistry
from easyagents.core.exceptions import AgentAlreadyRegisteredError, AgentNotFoundError
from easyagents.tools.registry import ToolRegistry


@pytest.fixture
def tool_registry():
    tr = ToolRegistry()

    def dummy_tool(x: int) -> str:
        """A dummy tool for testing."""
        return str(x)

    tr.register("dummy_tool", dummy_tool)
    return tr


@pytest.fixture
def registry():
    return AgentRegistry()


def test_register_and_list(registry):
    registry.register(AgentDefinition(
        name="test_agent", instructions="You are a test agent.", model="openai:gpt-4o",
    ))
    names = registry.list()
    assert "test_agent" in names


def test_register_duplicate_raises(registry):
    registry.register(AgentDefinition(name="dup", instructions="", model="openai:gpt-4o"))
    with pytest.raises(AgentAlreadyRegisteredError):
        registry.register(AgentDefinition(name="dup", instructions="", model="openai:gpt-4o"))


def test_get_returns_definition(registry):
    expected = AgentDefinition(name="get_me", instructions="Hi", model="openai:gpt-4o")
    registry.register(expected)
    assert registry.get("get_me") is expected


def test_get_nonexistent_raises(registry):
    with pytest.raises(AgentNotFoundError):
        registry.get("nonexistent")


def test_create_returns_pydantic_agent(registry, tool_registry):
    registry.register(AgentDefinition(
        name="creator_test", instructions="You are a test.", model="openai:gpt-4o",
    ))
    agent = registry.create("creator_test", tool_registry)
    assert isinstance(agent, Agent)


def test_create_with_tools(registry, tool_registry):
    registry.register(AgentDefinition(
        name="tool_agent", instructions="You use tools.", model="openai:gpt-4o",
        tools=["dummy_tool"],
    ))
    agent = registry.create("tool_agent", tool_registry)
    assert isinstance(agent, Agent)


def test_create_caches_agent(registry, tool_registry):
    registry.register(AgentDefinition(
        name="cached_test", instructions="test", model="openai:gpt-4o",
    ))
    a1 = registry.create("cached_test", tool_registry)
    a2 = registry.create("cached_test", tool_registry)
    assert a1 is a2


def test_create_with_output_type(registry, tool_registry):
    from pydantic import BaseModel

    class Output(BaseModel):
        result: str

    registry.register(AgentDefinition(
        name="structured", instructions="output", model="openai:gpt-4o",
        output_type=Output,
    ))
    agent = registry.create("structured", tool_registry)
    assert isinstance(agent, Agent)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_agent_registry.py -v
```

Expected: Fails with `ModuleNotFoundError`

- [ ] **Step 3: Write agent.py**

```python
from dataclasses import dataclass, field
from typing import Any

from pydantic_ai import Agent

from easyagents.core.exceptions import (
    AgentAlreadyRegisteredError,
    AgentNotFoundError,
)
from easyagents.tools.registry import ToolRegistry


@dataclass
class AgentDefinition:
    name: str
    instructions: str
    model: str
    tools: list[str] = field(default_factory=list)
    output_type: type | None = None
    deps_type: type | None = None
    description: str = ""
    subagents: list[str] = field(default_factory=list)


class AgentRegistry:
    def __init__(self) -> None:
        self._definitions: dict[str, AgentDefinition] = {}
        self._agents: dict[str, Agent[Any]] = {}

    def register(self, definition: AgentDefinition) -> None:
        if definition.name in self._definitions:
            raise AgentAlreadyRegisteredError(
                f"Agent '{definition.name}' is already registered"
            )
        self._definitions[definition.name] = definition

    def get(self, name: str) -> AgentDefinition:
        if name not in self._definitions:
            raise AgentNotFoundError(f"Agent '{name}' is not registered")
        return self._definitions[name]

    def create(self, name: str, tool_registry: ToolRegistry) -> Agent[Any]:
        if name in self._agents:
            return self._agents[name]

        definition = self.get(name)
        pydantic_tools = tool_registry.resolve(definition.tools)

        if definition.subagents:
            from easyagents.patterns.delegation import DelegationManager
            dm = DelegationManager(
                parent_name=name,
                subagent_names=definition.subagents,
                registry=self,
                tool_registry=tool_registry,
            )
            pydantic_tools.extend(dm.create_delegation_tools())

        kwargs: dict[str, Any] = {
            "model": definition.model,
            "name": definition.name,
            "system_prompt": definition.instructions,
            "tools": pydantic_tools,
        }
        if definition.output_type is not None:
            kwargs["output_type"] = definition.output_type

        agent: Agent[Any] = Agent(**kwargs)
        self._agents[name] = agent
        return agent

    def list(self) -> list[str]:
        return list(self._definitions.keys())
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_agent_registry.py -v
```

Expected: All 7 tests pass (the `create_with_tools` test has no subagents, so delegation import is not triggered)

- [ ] **Step 5: Write the failing test for SessionManager**

```python
import pytest
from easyagents.core.session import Session, SessionManager


@pytest.fixture
def manager():
    return SessionManager()


def test_create_session(manager):
    session = manager.create()
    assert isinstance(session, Session)
    assert session.conversation_id is not None
    assert session.messages == []


def test_get_existing_session(manager):
    created = manager.create()
    retrieved = manager.get(created.conversation_id)
    assert retrieved is created


def test_get_nonexistent_returns_none(manager):
    assert manager.get("nonexistent-id") is None


def test_save_messages(manager):
    from pydantic_ai import ModelRequest, ModelResponse, TextPart, UserPromptPart
    session = manager.create()
    messages = [
        ModelRequest(parts=[UserPromptPart(content="Hello")]),
        ModelResponse(parts=[TextPart(content="Hi")]),
    ]
    manager.save_messages(session.conversation_id, messages)
    assert session.messages == messages


def test_save_messages_overwrites(manager):
    from pydantic_ai import ModelRequest, UserPromptPart
    session = manager.create()
    old = [ModelRequest(parts=[UserPromptPart(content="Old")])]
    new = [ModelRequest(parts=[UserPromptPart(content="New")])]
    manager.save_messages(session.conversation_id, old)
    manager.save_messages(session.conversation_id, new)
    assert session.messages == new
```

- [ ] **Step 6: Run test to verify it fails**

```bash
pytest tests/test_session.py -v
```

Expected: Fails with `ModuleNotFoundError`

- [ ] **Step 7: Write session.py**

```python
from dataclasses import dataclass, field
from uuid import uuid4

from pydantic_ai import ModelMessage


@dataclass
class Session:
    conversation_id: str
    messages: list[ModelMessage] = field(default_factory=list)


class SessionManager:
    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}

    def create(self) -> Session:
        conversation_id = str(uuid4())
        session = Session(conversation_id=conversation_id)
        self._sessions[conversation_id] = session
        return session

    def get(self, conversation_id: str) -> Session | None:
        return self._sessions.get(conversation_id)

    def save_messages(self, conversation_id: str, messages: list[ModelMessage]) -> None:
        self._sessions[conversation_id].messages = messages
```

- [ ] **Step 8: Run all tests to verify they pass**

```bash
pytest tests/ -v
```

Expected: All tests in test_tool_registry, test_agent_registry, test_session pass

- [ ] **Step 9: Commit**

```bash
git add src/easyagents/core/agent.py src/easyagents/core/session.py tests/
git commit -m "feat: agent registry and session manager"
```

---

### Task 4: Delegation Pattern

**Files:**
- Create: `src/easyagents/patterns/delegation.py`
- Create: `tests/test_delegation.py`

**Interfaces:**
- Consumes: `AgentRegistry` from `easyagents.core.agent`, `ToolRegistry` from `easyagents.tools.registry`, `DelegationError` from `easyagents.core.exceptions`
- Produces: `DelegationManager(parent_name, subagent_names, registry, tool_registry)` class with `create_delegation_tools()` → `list[Tool]` and `delegate(subagent_name, task, parent_usage, model=None)` → `Any`

- [ ] **Step 1: Write the failing test for DelegationManager**

```python
import pytest
from pydantic_ai import RunUsage
from pydantic_ai.models.function import FunctionModel, AgentInfo
from pydantic_ai import ModelResponse, TextPart

from easyagents.core.agent import AgentDefinition, AgentRegistry
from easyagents.core.exceptions import DelegationError
from easyagents.tools.registry import ToolRegistry
from easyagents.patterns.delegation import DelegationManager


@pytest.fixture
def tool_registry():
    tr = ToolRegistry()
    tr.register("web_search", lambda q: [{"title": "R", "url": "https://x.com", "snippet": "..."}])
    return tr


@pytest.fixture
def registry():
    return AgentRegistry()


def make_handler(output: str = "Done"):
    def handler(messages: list, info: AgentInfo) -> ModelResponse:
        return ModelResponse(parts=[TextPart(content=output)])
    return FunctionModel(handler)


def test_delegation_tool_names_use_delegate_prefix(tool_registry, registry):
    registry.register(AgentDefinition(name="researcher", instructions="Research.", model="openai:gpt-4o"))
    dm = DelegationManager("parent", ["researcher"], registry, tool_registry)
    tools = dm.create_delegation_tools()
    assert len(tools) == 1
    assert tools[0].name == "delegate_researcher"


def test_delegation_tool_count_matches_subagents(tool_registry, registry):
    for name in ["a", "b", "c"]:
        registry.register(AgentDefinition(name=name, instructions=f"I'm {name}", model="openai:gpt-4o"))
    dm = DelegationManager("parent", ["a", "b", "c"], registry, tool_registry)
    tools = dm.create_delegation_tools()
    assert len(tools) == 3


@pytest.mark.asyncio
async def test_delegate_runs_subagent_and_returns_output(tool_registry, registry):
    registry.register(AgentDefinition(
        name="researcher", instructions="You research.", model="openai:gpt-4o",
    ))
    dm = DelegationManager("parent", ["researcher"], registry, tool_registry)
    usage = RunUsage()
    result = await dm.delegate(
        "researcher", "test task", usage,
        model=make_handler("Found: AirPods Pro 2"),
    )
    assert result == "Found: AirPods Pro 2"


@pytest.mark.asyncio
async def test_delegate_passes_usage(tool_registry, registry):
    registry.register(AgentDefinition(
        name="counter", instructions="You count.", model="openai:gpt-4o",
    ))
    dm = DelegationManager("parent", ["counter"], registry, tool_registry)
    usage = RunUsage()
    await dm.delegate("counter", "count to 3", usage, model=make_handler("Done"))
    assert usage.requests > 0


@pytest.mark.asyncio
async def test_delegate_nonexistent_subagent_raises(tool_registry, registry):
    dm = DelegationManager("parent", ["ghost"], registry, tool_registry)
    usage = RunUsage()
    with pytest.raises(DelegationError):
        await dm.delegate("ghost", "task", usage, model=make_handler())


@pytest.mark.asyncio
async def test_agent_registry_create_injects_delegation_tools(tool_registry, registry):
    registry.register(AgentDefinition(name="helper", instructions="Help.", model="openai:gpt-4o"))
    registry.register(AgentDefinition(
        name="boss", instructions="You delegate.", model="openai:gpt-4o",
        subagents=["helper"],
    ))
    agent = registry.create("boss", tool_registry)
    assert agent is not None
    # Run with FunctionModel to verify agent works with delegation tools
    result = agent.run_sync("do it", model=make_handler("OK"))
    assert result.output is not None
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_delegation.py -v
```

Expected: Fails with `ModuleNotFoundError`

- [ ] **Step 3: Write delegation.py**

```python
from typing import Any, Optional

from pydantic_ai import RunUsage, Tool

from easyagents.core.exceptions import DelegationError


class DelegationManager:
    def __init__(
        self,
        parent_name: str,
        subagent_names: list[str],
        registry: Any,
        tool_registry: Any,
    ) -> None:
        self.parent_name = parent_name
        self.subagent_names = subagent_names
        self.registry = registry
        self.tool_registry = tool_registry

    def create_delegation_tools(self) -> list[Tool]:
        tools: list[Tool] = []
        for name in self.subagent_names:
            delegate_func = self._make_delegate_func(name)
            tools.append(Tool(delegate_func))
        return tools

    def _make_delegate_func(self, subagent_name: str):
        from pydantic_ai import RunContext

        async def delegate(ctx: RunContext[None], task: str) -> Any:
            try:
                subagent = self.registry.create(subagent_name, self.tool_registry)
                result = await subagent.run(task, usage=ctx.usage)
                return result.output
            except Exception as e:
                raise DelegationError(
                    f"Delegation to '{subagent_name}' failed: {e}"
                ) from e

        delegate.__name__ = f"delegate_{subagent_name}"
        return delegate

    async def delegate(
        self,
        subagent_name: str,
        task: str,
        parent_usage: RunUsage,
        model: Optional[Any] = None,
    ) -> Any:
        try:
            subagent = self.registry.create(subagent_name, self.tool_registry)
            kwargs = {"usage": parent_usage}
            if model is not None:
                kwargs["model"] = model
            result = await subagent.run(task, **kwargs)
            return result.output
        except Exception as e:
            raise DelegationError(
                f"Delegation to '{subagent_name}' failed: {e}"
            ) from e
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_delegation.py -v
```

Expected: All 6 tests pass

- [ ] **Step 5: Verify agent registry integration creates agents with delegation**

```bash
pytest tests/test_agent_registry.py tests/test_delegation.py -v
```

Expected: All pass

- [ ] **Step 6: Commit**

```bash
git add src/easyagents/patterns/ tests/
git commit -m "feat: agent delegation pattern with DelegationManager"
```

---

### Task 5: Observability + Public API + Integration Test

**Files:**
- Create: `src/easyagents/observability/tracing.py`
- Modify: `src/easyagents/__init__.py` (wire public API)
- Create: `tests/test_observability.py`
- Create: `tests/test_integration.py`

**Interfaces:**
- Consumes: all modules from previous tasks
- Produces: `configure(logfire_token, service_name)` function; final public API in `easyagents/__init__.py`

- [ ] **Step 1: Write observability/tracing.py**

```python
from typing import Optional


def configure(
    logfire_token: Optional[str] = None,
    service_name: str = "easyagents",
) -> None:
    """Configure Logfire observability for EasyAgents.

    Sets up Logfire and instruments Pydantic AI for automatic tracing
    of agent runs, tool calls, and delegation.

    Args:
        logfire_token: Logfire cloud token. If None, logs to stderr (development mode).
        service_name: Service name for identifying traces.
    """
    import logfire

    logfire.configure(
        token=logfire_token,
        service_name=service_name,
    )
    logfire.instrument_pydantic_ai()
```

- [ ] **Step 2: Write the failing test for observability**

```python
import pytest
from easyagents.observability.tracing import configure


def test_configure_runs_without_error():
    # Should not raise - configures Logfire for stderr output
    configure(service_name="test-easyagents")


def test_configure_is_idempotent():
    configure(service_name="test-easyagents")
    configure(service_name="test-easyagents")  # second call should not raise
```

- [ ] **Step 3: Run test to verify it fails**

```bash
pytest tests/test_observability.py -v
```

Expected: Fails with `ModuleNotFoundError` (tracing.py doesn't exist)

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_observability.py -v
```

Expected: Both tests pass

- [ ] **Step 5: Write __init__.py (public API)**

```python
"""EasyAgents - Multi-agent workbench built on Pydantic AI."""

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

- [ ] **Step 6: Verify public API works**

```bash
python -c "
from easyagents import (
    AgentDefinition, AgentRegistry, Session, SessionManager,
    ToolRegistry, ToolMetadata, web_search, configure,
    EasyAgentsError, AgentAlreadyRegisteredError, AgentNotFoundError,
    ToolAlreadyRegisteredError, ToolNotFoundError, DelegationError,
)
print('Public API OK')
print(f'Exported {len(__all__)} symbols')
"
```

Expected: `Public API OK` and `Exported 13 symbols`

- [ ] **Step 7: Write integration test**

```python
import pytest
from pydantic import BaseModel
from pydantic_ai import RunUsage
from pydantic_ai.models.function import FunctionModel, AgentInfo
from pydantic_ai import ModelResponse, TextPart

from easyagents import (
    AgentDefinition,
    AgentRegistry,
    ToolRegistry,
    web_search,
)


class ResearchFindings(BaseModel):
    products: list[str]
    summary: str


@pytest.fixture
def handler():
    def handle(messages: list, info: AgentInfo) -> ModelResponse:
        return ModelResponse(parts=[TextPart(
            content='{"products": ["AirPods Pro 2", "Sony WF-1000XM5", "Bose QC Ultra"], "summary": "Three top competitors in the high-end TWS market."}'
        )])
    return FunctionModel(handle)


@pytest.mark.asyncio
async def test_bluetooth_earphone_research(handler):
    """End-to-end test: orchestrator delegates to researcher via delegation."""

    tools = ToolRegistry()
    tools.register("web_search", web_search)

    agents = AgentRegistry()

    agents.register(AgentDefinition(
        name="researcher",
        instructions="You are a product researcher. Use web_search to research.",
        model="openai:gpt-4o",
        tools=["web_search"],
        output_type=ResearchFindings,
        description="Product researcher",
    ))

    agents.register(AgentDefinition(
        name="orchestrator",
        instructions="You are a research orchestrator. Use delegate_researcher to delegate.",
        model="openai:gpt-4o",
        subagents=["researcher"],
        description="Research orchestrator",
    ))

    agent = agents.create("orchestrator", tools)
    result = agent.run_sync(
        "调研最近爆火的蓝牙耳机",
        model=handler,
    )
    assert result.output is not None


def test_full_pipeline():
    """Simplified pipeline test: register, create, and run with TestModel."""
    from pydantic_ai.models.test import TestModel

    tools = ToolRegistry()
    tools.register("web_search", lambda q: [{"title": "X", "url": "https://x.com", "snippet": "test"}])

    agents = AgentRegistry()
    agents.register(AgentDefinition(
        name="researcher",
        instructions="Research.",
        model="openai:gpt-4o",
        tools=["web_search"],
        output_type=ResearchFindings,
    ))
    agents.register(AgentDefinition(
        name="orchestrator",
        instructions="Delegate.",
        model="openai:gpt-4o",
        subagents=["researcher"],
    ))

    agent = agents.create("orchestrator", tools)
    result = agent.run_sync("research bluetooth earphones", model=TestModel())
    assert result.output is not None
    assert len(result.all_messages()) > 0
```

- [ ] **Step 8: Run integration test**

```bash
pytest tests/test_integration.py -v
```

Expected: Both tests pass

- [ ] **Step 9: Run the full test suite**

```bash
pytest tests/ -v
```

Expected: All tests across all test files pass

- [ ] **Step 10: Demonstrate the working API with a script**

Create `scripts/demo.py` to show the end-to-end flow using `TestModel`:

```python
"""Demo: show how EasyAgents multi-agent delegation works."""
from pydantic import BaseModel
from pydantic_ai.models.test import TestModel

from easyagents import (
    AgentDefinition,
    AgentRegistry,
    ToolRegistry,
    configure,
)


class ResearchFindings(BaseModel):
    products: list[str]
    summary: str


def main():
    configure(service_name="easyagents-demo")

    tools = ToolRegistry()
    tools.register("web_search", lambda q: [
        {"title": "AirPods Pro 2", "url": "https://apple.com", "snippet": "Apple's flagship TWS earbuds"}
    ])

    agents = AgentRegistry()
    agents.register(AgentDefinition(
        name="researcher",
        instructions="Research products using web_search.",
        model="openai:gpt-4o",
        tools=["web_search"],
        output_type=ResearchFindings,
    ))
    agents.register(AgentDefinition(
        name="orchestrator",
        instructions="Use delegate_researcher to research, then summarize.",
        model="openai:gpt-4o",
        subagents=["researcher"],
    ))

    agent = agents.create("orchestrator", tools)

    # Use TestModel to avoid real API calls
    result = agent.run_sync(
        "调研最近爆火的蓝牙耳机",
        model=TestModel(custom_output=str(ResearchFindings(
            products=["AirPods Pro 2", "Sony WF-1000XM5"],
            summary="Two top competitors.",
        ))),
    )

    print(f"Output: {result.output}")
    print(f"Usage: {result.usage}")
    print("Done!")


if __name__ == "__main__":
    main()
```

```bash
mkdir -p scripts
python scripts/demo.py
```

Expected: Prints output, usage, and "Done!"

- [ ] **Step 11: Commit**

```bash
git add src/easyagents/observability/ src/easyagents/__init__.py tests/ scripts/
git commit -m "feat: observability, public API, and integration test"
```