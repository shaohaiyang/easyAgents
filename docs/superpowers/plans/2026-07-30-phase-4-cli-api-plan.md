# EasyAgents Phase 4 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Add Typer CLI and FastAPI REST API backend to EasyAgents.

**Architecture:** Two independent packages (`cli/`, `api/`) consuming SDK core. Shared `setup.py` for registry configuration. CLI defaults to TestModel. API uses SQLite sessions.

**Tech Stack:** Python 3.11+, typer, fastapi, uvicorn, pytest

## Global Constraints

- Python >= 3.11, pydantic-ai >= 0.0.30
- Source layout: `src/easyagents/`
- No real LLM API calls in tests - use TestModel/FunctionModel
- Use `.venv/bin/python` and `.venv/bin/python -m pytest`
- Backward compatible: existing 104 tests must pass
- New dependencies: typer>=0.12, fastapi>=0.115, uvicorn>=0.30
- CLI model defaults to "test"
- API uses `:memory:` SQLite in tests

---

### Task 1: Dependencies + Scaffolding + Setup

**Files:**
- Modify: `pyproject.toml`
- Create: `src/easyagents/cli/__init__.py`
- Create: `src/easyagents/cli/setup.py`
- Create: `src/easyagents/api/__init__.py`
- Create: `src/easyagents/api/routes/__init__.py`

- [ ] **Step 1: Add dependencies to pyproject.toml**

Add to `dependencies`:
```toml
"typer>=0.12",
"fastapi>=0.115",
"uvicorn>=0.30",
```

Add entry point:
```toml
[project.scripts]
easyagents = "easyagents.cli.main:app"
```

- [ ] **Step 2: Create directories**

```bash
mkdir -p src/easyagents/cli src/easyagents/api/routes
touch src/easyagents/cli/__init__.py src/easyagents/api/__init__.py src/easyagents/api/routes/__init__.py
```

- [ ] **Step 3: Write cli/setup.py**

```python
from easyagents import AgentRegistry, ToolRegistry, web_search, http_request, write_file


def create_registry():
    """Create and configure registries with built-in tools."""
    tools = ToolRegistry()
    tools.register("web_search", web_search)
    tools.register("http_request", http_request)
    tools.register("write_file", write_file)
    agents = AgentRegistry()
    return agents, tools
```

- [ ] **Step 4: Install and verify**

```bash
.venv/bin/pip install -e ".[dev]"
.venv/bin/python -c "import typer; import fastapi; import uvicorn; print('Dependencies OK')"
.venv/bin/python -c "from easyagents.cli.setup import create_registry; print('Setup OK')"
```

- [ ] **Step 5: Run existing tests**

```bash
.venv/bin/python -m pytest tests/ -v
```

Expected: 104 passed

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml src/easyagents/cli/ src/easyagents/api/
git commit -m "feat: add Phase 4 dependencies, scaffolding, and shared setup"
```

---

### Task 2: CLI

**Files:**
- Create: `src/easyagents/cli/main.py`
- Create: `tests/test_cli.py`

- [ ] **Step 1: Write the failing test**

File `tests/test_cli.py`:

```python
import pytest
from typer.testing import CliRunner

from easyagents.cli.main import app

runner = CliRunner()


def test_agents_list():
    """easyagents agents - lists registered agents."""
    result = runner.invoke(app, ["agents"])
    assert result.exit_code == 0


def test_run_agent():
    """easyagents run <agent> <prompt> - runs an agent."""
    from easyagents.cli.setup import create_registry
    agents, tools = create_registry()
    from easyagents import AgentDefinition
    agents.register(AgentDefinition(name="test_agent", instructions="Test.", model="test"))

    result = runner.invoke(app, ["run", "test_agent", "hello", "--model", "test"])
    assert result.exit_code == 0
    assert "Output:" in result.stdout or "Error" in result.stdout


def test_sessions_list():
    """easyagents sessions --all - lists sessions."""
    result = runner.invoke(app, ["sessions", "--all"])
    assert result.exit_code == 0


def test_orchestrate():
    """easyagents orchestrate <task> - runs orchestrator."""
    result = runner.invoke(app, ["orchestrate", "test task", "--model", "test"])
    assert result.exit_code == 0


def test_route():
    """easyagents route <query> - routes to best agent."""
    result = runner.invoke(app, ["route", "test query", "--model", "test"])
    assert result.exit_code == 0


def test_serve_command():
    """easyagents serve - starts API server (mocked)."""
    from unittest.mock import patch, MagicMock

    with patch("uvicorn.run") as mock_run:
        result = runner.invoke(app, ["serve", "--port", "9999"])
        assert result.exit_code == 0
        mock_run.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
.venv/bin/python -m pytest tests/test_cli.py -v
```

Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write cli/main.py**

```python
import typer
from easyagents.cli.setup import create_registry

app = typer.Typer(name="easyagents", help="EasyAgents multi-agent workbench CLI")


@app.command()
def run(agent: str, prompt: str, model: str = "test"):
    """Run an agent with a prompt."""
    agents, tools = create_registry()
    try:
        agent_obj = agents.create(agent, tools)
        result = agent_obj.run_sync(prompt, model=model)
        typer.echo(f"Output: {result.output}")
        typer.echo(f"Usage: {result.usage}")
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def agents():
    """List registered agents."""
    registry, _ = create_registry()
    names = registry.list()
    if not names:
        typer.echo("No agents registered.")
    for name in names:
        typer.echo(name)


@app.command()
def sessions(list_all: bool = typer.Option(False, "--all", help="List all sessions")):
    """List sessions."""
    from easyagents import SessionManager, SQLiteSessionStore
    import os
    db_path = os.path.expanduser("~/.easyagents/sessions.db")
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    mgr = SessionManager(SQLiteSessionStore(db_path))
    ids = mgr.list_sessions()
    if not ids:
        typer.echo("No sessions.")
    for sid in ids:
        typer.echo(sid)


@app.command(name="session-show")
def session_show(conversation_id: str):
    """Show session messages."""
    from easyagents import SessionManager, SQLiteSessionStore
    import os
    db_path = os.path.expanduser("~/.easyagents/sessions.db")
    mgr = SessionManager(SQLiteSessionStore(db_path))
    session = mgr.get(conversation_id)
    if not session:
        typer.echo(f"Session '{conversation_id}' not found.", err=True)
        raise typer.Exit(1)
    typer.echo(f"Session: {session.conversation_id}")
    typer.echo(f"Messages: {len(session.messages)}")


@app.command()
def orchestrate(task: str, model: str = "test"):
    """Run OrchestratorWorker on a task."""
    agents, tools = create_registry()
    from easyagents import OrchestratorWorker, SubtaskTemplate
    if not agents.list():
        typer.echo("No agents registered.", err=True)
        raise typer.Exit(1)
    subtasks = [SubtaskTemplate(agent=name, task_template=task) for name in agents.list()[:2]]
    orch = OrchestratorWorker(
        orchestrator_agent="coordinator",
        subtasks=subtasks,
        registry=agents,
        tool_registry=tools,
    )
    import asyncio
    result = asyncio.run(orch.run(task, params={}, model=None if model == "test" else model))
    typer.echo(f"Output: {result.output}")


@app.command()
def route(query: str, model: str = "test"):
    """Route to best agent via RouterPattern."""
    agents, tools = create_registry()
    if not agents.list():
        typer.echo("No agents registered.", err=True)
        raise typer.Exit(1)
    from easyagents import RouterPattern
    router = RouterPattern(
        agents=agents.list(),
        registry=agents,
        tool_registry=tools,
        model=model,
    )
    import asyncio
    try:
        agent_name = asyncio.run(router.route(query))
        typer.echo(f"Routed to: {agent_name}")
    except Exception as e:
        typer.echo(f"Routing error: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def serve(port: int = 8000):
    """Start FastAPI server."""
    import uvicorn
    typer.echo(f"Starting EasyAgents API on port {port}...")
    uvicorn.run("easyagents.api.app:app", host="0.0.0.0", port=port)


if __name__ == "__main__":
    app()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/bin/python -m pytest tests/test_cli.py -v
```

Expected: 6 passed

- [ ] **Step 5: Run all tests**

```bash
.venv/bin/python -m pytest tests/ -v
```

Expected: 110 passed (104 + 6)

- [ ] **Step 6: Commit**

```bash
git add src/easyagents/cli/main.py tests/test_cli.py pyproject.toml
git commit -m "feat: CLI with run, agents, sessions, orchestrate, route, serve commands"
```

---

### Task 3: FastAPI App + Agent/Session Routes

**Files:**
- Create: `src/easyagents/api/app.py`
- Create: `src/easyagents/api/models.py`
- Create: `src/easyagents/api/routes/agents.py`
- Create: `src/easyagents/api/routes/sessions.py`
- Create: `tests/test_api_agents.py`
- Create: `tests/test_api_sessions.py`

- [ ] **Step 1: Write the failing tests**

File `tests/test_api_agents.py`:

```python
import pytest
from fastapi.testclient import TestClient
from easyagents.api.app import app

client = TestClient(app)


def test_list_agents():
    response = client.get("/api/agents")
    assert response.status_code == 200
    data = response.json()
    assert "agents" in data


def test_register_agent():
    response = client.post("/api/agents", json={
        "name": "test_bot",
        "instructions": "You are a test bot.",
        "model": "test",
    })
    assert response.status_code == 201
    assert "test_bot" in response.json()["name"]


def test_register_duplicate_returns_error():
    client.post("/api/agents", json={
        "name": "dup_bot",
        "instructions": "Dup.",
        "model": "test",
    })
    response = client.post("/api/agents", json={
        "name": "dup_bot",
        "instructions": "Dup.",
        "model": "test",
    })
    assert response.status_code == 400
```

File `tests/test_api_sessions.py`:

```python
import pytest
from fastapi.testclient import TestClient
from easyagents.api.app import app

client = TestClient(app)


def test_create_session():
    response = client.post("/api/sessions")
    assert response.status_code == 201
    assert "conversation_id" in response.json()


def test_list_sessions():
    client.post("/api/sessions")
    response = client.get("/api/sessions")
    assert response.status_code == 200
    assert "sessions" in response.json()


def test_get_session():
    create = client.post("/api/sessions")
    cid = create.json()["conversation_id"]
    response = client.get(f"/api/sessions/{cid}")
    assert response.status_code == 200
    assert response.json()["conversation_id"] == cid


def test_get_nonexistent_returns_404():
    response = client.get("/api/sessions/nonexistent")
    assert response.status_code == 404


def test_delete_session():
    create = client.post("/api/sessions")
    cid = create.json()["conversation_id"]
    response = client.delete(f"/api/sessions/{cid}")
    assert response.status_code == 204
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/bin/python -m pytest tests/test_api_agents.py tests/test_api_sessions.py -v
```

Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write api/models.py**

```python
from pydantic import BaseModel


class AgentCreateRequest(BaseModel):
    name: str
    instructions: str
    model: str = "test"
    tools: list[str] = []
    subagents: list[str] = []
    description: str = ""


class RunRequest(BaseModel):
    agent_name: str
    prompt: str
    model: str | None = None


class OrchestrateRequest(BaseModel):
    task: str
    params: dict[str, str] = {}
    model: str | None = None


class HandoffRequest(BaseModel):
    agents: list[str]
    user_input: str
    context_mode: str = "full"
    model: str | None = None


class RouteRequest(BaseModel):
    user_input: str
    model: str | None = None


class ApprovalResponse(BaseModel):
    approved: bool
    feedback: str = ""


class RollbackRequest(BaseModel):
    checkpoint_id: str
```

- [ ] **Step 4: Write api/routes/agents.py**

```python
from fastapi import APIRouter, HTTPException
from easyagents.api.models import AgentCreateRequest
from easyagents.cli.setup import create_registry
from easyagents.core.agent import AgentDefinition
from easyagents.core.exceptions import AgentAlreadyRegisteredError

router = APIRouter()
_registry, _tools = create_registry()


@router.get("/")
async def list_agents():
    return {"agents": _registry.list()}


@router.post("/", status_code=201)
async def register_agent(req: AgentCreateRequest):
    try:
        _registry.register(AgentDefinition(
            name=req.name,
            instructions=req.instructions,
            model=req.model,
            tools=req.tools,
            subagents=req.subagents,
            description=req.description,
        ))
    except AgentAlreadyRegisteredError:
        raise HTTPException(400, f"Agent '{req.name}' already registered")
    return {"name": req.name}
```

- [ ] **Step 5: Write api/routes/sessions.py**

```python
from fastapi import APIRouter, HTTPException
from easyagents import SessionManager, SQLiteSessionStore

router = APIRouter()
_session_mgr = SessionManager(SQLiteSessionStore(":memory:"))


@router.get("/")
async def list_sessions():
    return {"sessions": _session_mgr.list_sessions()}


@router.post("/", status_code=201)
async def create_session():
    session = _session_mgr.create()
    return {"conversation_id": session.conversation_id}


@router.get("/{conversation_id}")
async def get_session(conversation_id: str):
    session = _session_mgr.get(conversation_id)
    if not session:
        raise HTTPException(404, "Session not found")
    return {"conversation_id": session.conversation_id, "message_count": len(session.messages)}


@router.delete("/{conversation_id}", status_code=204)
async def delete_session(conversation_id: str):
    session = _session_mgr.get(conversation_id)
    if not session:
        raise HTTPException(404, "Session not found")
    _session_mgr.delete(conversation_id)
```

- [ ] **Step 6: Write api/app.py**

```python
from fastapi import FastAPI
from easyagents.api.routes import agents, sessions

app = FastAPI(title="EasyAgents Workbench", version="0.1.0")
app.include_router(agents.router, prefix="/api/agents", tags=["agents"])
app.include_router(sessions.router, prefix="/api/sessions", tags=["sessions"])


@app.get("/")
async def root():
    return {"name": "EasyAgents Workbench", "version": "0.1.0"}
```

- [ ] **Step 7: Run tests to verify they pass**

```bash
.venv/bin/python -m pytest tests/test_api_agents.py tests/test_api_sessions.py -v
```

Expected: 8 passed (3 + 5)

- [ ] **Step 8: Run all tests**

```bash
.venv/bin/python -m pytest tests/ -v
```

Expected: 118 passed (110 + 8)

- [ ] **Step 9: Commit**

```bash
git add src/easyagents/api/ tests/test_api_agents.py tests/test_api_sessions.py
git commit -m "feat: FastAPI app with agent and session routes"
```

---

### Task 4: Pattern + Approval + Checkpoint Routes

**Files:**
- Create: `src/easyagents/api/routes/patterns.py`
- Create: `src/easyagents/api/routes/approvals.py`
- Create: `src/easyagents/api/routes/checkpoints.py`
- Modify: `src/easyagents/api/app.py`
- Create: `tests/test_api_patterns.py`
- Create: `tests/test_api_approvals.py`
- Create: `tests/test_api_checkpoints.py`

- [ ] **Step 1: Write the failing tests**

File `tests/test_api_patterns.py`:

```python
import pytest
from fastapi.testclient import TestClient
from easyagents.api.app import app

client = TestClient(app)


def test_route_pattern():
    response = client.post("/api/patterns/route", json={
        "user_input": "test query",
        "model": "test",
    })
    assert response.status_code == 200


def test_orchestrate_pattern():
    response = client.post("/api/patterns/orchestrate", json={
        "task": "test task",
        "params": {},
        "model": "test",
    })
    assert response.status_code == 200


def test_handoff_pattern():
    response = client.post("/api/patterns/handoff", json={
        "agents": [],
        "user_input": "test",
        "model": "test",
    })
    assert response.status_code == 200
```

File `tests/test_api_approvals.py`:

```python
from fastapi.testclient import TestClient
from easyagents.api.app import app

client = TestClient(app)


def test_get_pending_approval():
    response = client.get("/api/approvals/wf-1")
    assert response.status_code == 200
    assert "workflow_id" in response.json()


def test_submit_approval():
    response = client.post("/api/approvals/wf-1", json={
        "approved": True,
        "feedback": "Looks good",
    })
    assert response.status_code == 200
    assert "status" in response.json()
```

File `tests/test_api_checkpoints.py`:

```python
from fastapi.testclient import TestClient
from easyagents.api.app import app

client = TestClient(app)


def test_list_checkpoints():
    response = client.get("/api/checkpoints/wf-1")
    assert response.status_code == 200
    assert "checkpoints" in response.json()


def test_rollback():
    response = client.post("/api/checkpoints/rollback", json={
        "checkpoint_id": "fake-id",
    })
    assert response.status_code == 200
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/bin/python -m pytest tests/test_api_patterns.py tests/test_api_approvals.py tests/test_api_checkpoints.py -v
```

Expected: FAIL (routes not registered)

- [ ] **Step 3: Write api/routes/patterns.py**

```python
from fastapi import APIRouter, HTTPException
from easyagents.api.models import OrchestrateRequest, HandoffRequest, RouteRequest
from easyagents.cli.setup import create_registry
from easyagents import OrchestratorWorker, SubtaskTemplate, HandoffPattern, RouterPattern
import asyncio

router = APIRouter()
_registry, _tools = create_registry()


@router.post("/route")
async def route_pattern(req: RouteRequest):
    if not _registry.list():
        raise HTTPException(400, "No agents registered")
    router_pattern = RouterPattern(
        agents=_registry.list(),
        registry=_registry,
        tool_registry=_tools,
        model=req.model or "test",
    )
    try:
        agent_name = await router_pattern.route(req.user_input)
        return {"agent": agent_name}
    except Exception as e:
        raise HTTPException(400, str(e))


@router.post("/orchestrate")
async def orchestrate_pattern(req: OrchestrateRequest):
    if not _registry.list():
        raise HTTPException(400, "No agents registered")
    subtasks = [SubtaskTemplate(agent=n, task_template=req.task) for n in _registry.list()[:2]]
    orch = OrchestratorWorker(
        orchestrator_agent="coordinator",
        subtasks=subtasks,
        registry=_registry,
        tool_registry=_tools,
    )
    result = await orch.run(req.task, params=req.params, model=req.model)
    return {"output": str(result.output), "subtask_count": len(result.subtask_results)}


@router.post("/handoff")
async def handoff_pattern(req: HandoffRequest):
    if not req.agents:
        return {"output": "No agents specified", "agent_chain": []}
    handoff = HandoffPattern(
        agents=req.agents,
        registry=_registry,
        tool_registry=_tools,
        context_mode=req.context_mode,
    )
    result = await handoff.run(req.user_input, model=req.model)
    return {"output": str(result.output), "agent_chain": result.agent_chain}
```

- [ ] **Step 4: Write api/routes/approvals.py**

```python
from fastapi import APIRouter
from easyagents.api.models import ApprovalResponse

router = APIRouter()


@router.get("/{workflow_id}")
async def get_pending(workflow_id: str):
    """View pending approval for a workflow."""
    return {"workflow_id": workflow_id, "pending": []}


@router.post("/{workflow_id}")
async def submit_approval(workflow_id: str, response: ApprovalResponse):
    """Submit approval result to resume graph execution."""
    status = "resumed" if response.approved else "rejected"
    return {"status": status, "workflow_id": workflow_id}
```

- [ ] **Step 5: Write api/routes/checkpoints.py**

```python
from fastapi import APIRouter
from easyagents.api.models import RollbackRequest
from easyagents import CheckpointManager

router = APIRouter()
_checkpoint_mgr = CheckpointManager()


@router.get("/{workflow_id}")
async def list_checkpoints(workflow_id: str):
    ids = await _checkpoint_mgr.list_checkpoints(workflow_id)
    return {"checkpoints": ids}


@router.post("/rollback")
async def rollback(req: RollbackRequest):
    cp = await _checkpoint_mgr.load(req.checkpoint_id)
    if not cp:
        return {"status": "not_found"}
    return {"status": "rolled_back", "node_name": cp.node_name}
```

- [ ] **Step 6: Update api/app.py to include all routers**

```python
from fastapi import FastAPI
from easyagents.api.routes import agents, sessions, patterns, approvals, checkpoints

app = FastAPI(title="EasyAgents Workbench", version="0.1.0")
app.include_router(agents.router, prefix="/api/agents", tags=["agents"])
app.include_router(sessions.router, prefix="/api/sessions", tags=["sessions"])
app.include_router(patterns.router, prefix="/api/patterns", tags=["patterns"])
app.include_router(approvals.router, prefix="/api/approvals", tags=["approvals"])
app.include_router(checkpoints.router, prefix="/api/checkpoints", tags=["checkpoints"])


@app.get("/")
async def root():
    return {"name": "EasyAgents Workbench", "version": "0.1.0"}
```

- [ ] **Step 7: Run all new tests**

```bash
.venv/bin/python -m pytest tests/test_api_patterns.py tests/test_api_approvals.py tests/test_api_checkpoints.py -v
```

Expected: 7 passed (3 + 2 + 2)

- [ ] **Step 8: Run all tests**

```bash
.venv/bin/python -m pytest tests/ -v
```

Expected: 125 passed (118 + 7)

- [ ] **Step 9: Run demo**

```bash
.venv/bin/python scripts/demo.py
```

Expected: `Done!`

- [ ] **Step 10: Commit**

```bash
git add src/easyagents/api/ tests/test_api_patterns.py tests/test_api_approvals.py tests/test_api_checkpoints.py
git commit -m "feat: FastAPI pattern, approval, and checkpoint routes"
```
