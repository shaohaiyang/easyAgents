# EasyAgents Phase 4 - CLI and FastAPI Backend

> Date: 2026-07-30
>
> Status: Draft
>
> Depends on: Phase 3 - complete (104 tests passing)

## 1. Overview

Phase 4 adds two independent interface layers to the EasyAgents SDK:

1. **CLI** - Typer-based command-line interface for running agents, managing sessions, and executing patterns
2. **FastAPI backend** - REST API exposing all SDK capabilities: agent management, sessions, patterns, HITL approvals, and checkpoints

### 1.1 Design Principles

- **Independent modules** - `cli/` and `api/` are separate packages, both consuming SDK core
- **Shared setup** - Both use a common `setup.py` for agent/tool registry configuration
- **TestModel default** - CLI defaults to `model="test"` to avoid accidental API costs
- **No auth** - Phase 4 has no authentication; Phase 5 Web UI will add it
- **SQLite persistence** - Both CLI and API use SQLiteSessionStore for session persistence

### 1.2 Architecture

```
┌─────────────────────┬────────────────────────┐
│   CLI (typer)       │   FastAPI (uvicorn)    │
│   easyagents cmd    │   :8000/api/*          │
├─────────────────────┴────────────────────────┤
│              Setup (shared config)            │
├───────────────────────────────────────────────┤
│              SDK Core (MVP - Phase 3)         │
│  AgentRegistry . Patterns . Workflows         │
│  SessionManager . ContextManager . Tools      │
├───────────────────────────────────────────────┤
│              Pydantic AI + pydantic_graph     │
└───────────────────────────────────────────────┘
```

## 2. Module Structure

```
easyagents/
├── cli/                      # NEW
│   ├── __init__.py
│   ├── main.py               # Typer app + commands
│   └── setup.py              # create_registry() factory
├── api/                      # NEW
│   ├── __init__.py
│   ├── app.py                # FastAPI app + router wiring
│   ├── models.py             # Request/response Pydantic models
│   └── routes/
│       ├── __init__.py
│       ├── agents.py         # Agent CRUD
│       ├── sessions.py       # Session CRUD + run
│       ├── patterns.py       # Orchestrate, handoff, route
│       ├── approvals.py      # HITL approval endpoints
│       └── checkpoints.py    # Checkpoint list + rollback
└── ... (existing SDK core unchanged)
```

## 3. CLI

### 3.1 Setup

`cli/setup.py` provides a factory function for agent/tool registry configuration:

```python
def create_registry() -> tuple[AgentRegistry, ToolRegistry]:
    """Create and configure registries with built-in tools."""
    tools = ToolRegistry()
    tools.register("web_search", web_search)
    tools.register("http_request", http_request)
    tools.register("write_file", write_file)
    agents = AgentRegistry()
    return agents, tools
```

### 3.2 Commands

```python
import typer
app = typer.Typer(name="easyagents")

@app.command()
def run(agent: str, prompt: str, model: str = "test"):
    """Run an agent with a prompt."""

@app.command()
def agents():
    """List registered agents."""

@app.command()
def sessions(list_all: bool = typer.Option(False, "--all")):
    """List sessions."""

@app.command()
def session_show(conversation_id: str):
    """Show session messages."""

@app.command()
def orchestrate(task: str, agent: str = "coordinator"):
    """Run OrchestratorWorker."""

@app.command()
def route(query: str):
    """Route to best agent via RouterPattern."""

@app.command()
def serve(port: int = 8000):
    """Start FastAPI server."""
    import uvicorn
    uvicorn.run("easyagents.api.app:app", host="0.0.0.0", port=port)
```

### 3.3 Entry Point

```toml
[project.scripts]
easyagents = "easyagents.cli.main:app"
```

### 3.4 Design Decisions

- **Model defaults to "test"**: Prevents accidental API costs. Use `--model openai:gpt-4o` for real LLM.
- **Session persistence**: CLI uses SQLiteSessionStore with `~/.easyagents/sessions.db`
- **Output format**: Text by default, `--json` flag for JSON output
- **Configuration**: Hardcoded in setup.py for Phase 4. Future: `~/.easyagents/config.toml`

## 4. FastAPI Backend

### 4.1 App

```python
from fastapi import FastAPI
from easyagents.api.routes import agents, sessions, patterns, approvals, checkpoints

app = FastAPI(title="EasyAgents Workbench", version="0.1.0")
app.include_router(agents.router, prefix="/api/agents", tags=["agents"])
app.include_router(sessions.router, prefix="/api/sessions", tags=["sessions"])
app.include_router(patterns.router, prefix="/api/patterns", tags=["patterns"])
app.include_router(approvals.router, prefix="/api/approvals", tags=["approvals"])
app.include_router(checkpoints.router, prefix="/api/checkpoints", tags=["checkpoints"])
```

### 4.2 Request/Response Models

```python
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

### 4.3 Endpoints

```
GET    /api/agents                     # List agents
POST   /api/agents                     # Register agent
GET    /api/sessions                   # List sessions
POST   /api/sessions                   # Create session
GET    /api/sessions/{id}              # Session details
DELETE /api/sessions/{id}              # Delete session
POST   /api/sessions/{id}/run          # Run agent in session
POST   /api/patterns/orchestrate       # Run OrchestratorWorker
POST   /api/patterns/handoff           # Run HandoffPattern
POST   /api/patterns/route             # Run RouterPattern
GET    /api/approvals/{id}             # View pending approval
POST   /api/approvals/{id}             # Submit approval result
GET    /api/checkpoints/{workflow_id}  # List checkpoints
POST   /api/checkpoints/rollback       # Rollback to checkpoint
```

### 4.4 Design Decisions

- **Global singletons**: SessionManager and AgentRegistry initialized at module level (MVP simplification)
- **Async endpoints**: All routes use `async def` matching SDK's async API
- **Error handling**: HTTP 404 for not found, 400 for bad request, 500 for internal errors
- **Approval API**: Phase 4 provides interface skeleton; full HITL state persistence in Phase 5
- **No authentication**: Added in Phase 5 with Web UI

## 5. Dependencies

### New Required Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `typer` | `>=0.12` | CLI framework |
| `fastapi` | `>=0.115` | REST API framework |
| `uvicorn` | `>=0.30` | ASGI server |

### Existing (no changes)

All Phase 1-3 dependencies remain unchanged.

## 6. Testing Strategy

### 6.1 New Test Files

| File | Coverage |
|------|----------|
| `test_cli.py` | run, agents list, sessions list, orchestrate, route, serve (mock uvicorn) |
| `test_api_agents.py` | GET/POST /api/agents |
| `test_api_sessions.py` | Create, list, detail, delete, run agent |
| `test_api_patterns.py` | Orchestrate, handoff, route endpoints |
| `test_api_approvals.py` | Pending, approve/reject |
| `test_api_checkpoints.py` | List, rollback |

### 6.2 Testing Approach

- **CLI**: `typer.testing.CliRunner` invokes commands, asserts on stdout
- **API**: FastAPI `TestClient` (sync) or `httpx.AsyncClient` with ASGI transport
- **All tests use TestModel/FunctionModel** - no real LLM calls
- **API tests use `:memory:` SQLite** for test isolation

### 6.3 Expected Test Count

| Module | New Tests |
|--------|-----------|
| CLI | ~6 |
| API agents | ~3 |
| API sessions | ~5 |
| API patterns | ~3 |
| API approvals | ~2 |
| API checkpoints | ~2 |
| **Total new** | **~21** |
| **Total (with existing 104)** | **~125** |

## 7. Out of Scope (Phase 5+)

- Web UI (frontend)
- Authentication / authorization
- WebSocket support for streaming
- Configuration file (`~/.easyagents/config.toml`)
- Full HITL state persistence (workflow state store)
- Rate limiting
- API documentation generation (OpenAPI/Swagger is auto-generated by FastAPI but not customized)
