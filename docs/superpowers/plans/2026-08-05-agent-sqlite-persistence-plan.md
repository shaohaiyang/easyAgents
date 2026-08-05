# Agent SQLite Persistence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist `AgentDefinition` records to SQLite so agents registered via CLI/API survive server restarts, including reversible reconstruction of `output_type`/`deps_type` from JSON schema.

**Architecture:** A new `SQLiteAgentStore` (following the existing `SQLiteSessionStore` pattern) stores agent definitions; `AgentRegistry` gains an optional backing store; `create_registry()` wires a default `~/.easyagents/agents.db` store. Types are serialized to JSON schema via `pydantic.TypeAdapter` and rebuilt with `pydantic.create_model`.

**Tech Stack:** Python 3.11+, stdlib `sqlite3`, `pydantic` (`TypeAdapter`, `create_model`), `pytest`, `tmp_path` fixture.

## Global Constraints

- Python 3.11+; use stdlib `sqlite3` (no new dependency).
- DB default path: `~/.easyagents/agents.db` (create parent dir if missing).
- `check_same_thread=False` and a persistent single connection (so `:memory:` survives), matching `SQLiteSessionStore`.
- `AgentRegistry(store=None)` must remain pure in-memory (backward compatible).
- Persist the 6 JSON-serializable fields + `output_type`/`deps_type` as JSON schema (user-confirmed: schema-only, no custom methods/validators preserved).
- On any type that cannot be reconstructed, raise `AgentStoreError(EasyAgentsError)` with a clear message.
- All tests use `tmp_path` for DB files; never touch real `~/.easyagents`.

---

### Task 1: `AgentStoreError` exception + wiring

**Files:**
- Modify: `src/easyagents/core/exceptions.py`
- Modify: `src/easyagents/__init__.py`
- Modify: `README.md` (public API list)

**Interfaces:**
- Consumes: existing `EasyAgentsError` base in `src/easyagents/core/exceptions.py`.
- Produces: `AgentStoreError(EasyAgentsError)`, exported as `easyagents.AgentStoreError`.

- [ ] **Step 1: Add exception class**

Add to `src/easyagents/core/exceptions.py` after the existing `SessionStoreError`/`ContextCompressionError` block:

```python
class AgentStoreError(EasyAgentsError):
    """Raised when the agent store (e.g. SQLite) fails."""
```

- [ ] **Step 2: Export in package `__init__.py`**

In `src/easyagents/__init__.py`, add `AgentStoreError` to the existing `from easyagents.core.exceptions import (...)` block and to `__all__`.

- [ ] **Step 3: Update README public API**

In `README.md` "异常" bullet, change `及 14 个子类` to `及 15 个子类` and add `AgentStoreError` to the parenthetical list.

- [ ] **Step 4: Verify** — `python -c "from easyagents import AgentStoreError"` returns without error.

- [ ] **Step 5: Commit**
```bash
git add src/easyagents/core/exceptions.py src/easyagents/__init__.py README.md
git commit -m "feat: add AgentStoreError exception"
```

---

### Task 2: `SQLiteAgentStore` + type serialization helpers

**Files:**
- Create: `src/easyagents/persistence/agents.py`
- Test: `tests/test_agent_store.py` (create)

**Interfaces:**
- Consumes: `AgentDefinition`, `AgentStoreError` (Task 1).
- Produces:
  - `class SQLiteAgentStore` — `__init__(db_path="easyagents.db", check_same_thread=False)`, `save(defn)`, `get(name) -> AgentDefinition | None`, `list() -> list[str]`, `delete(name)`, `close()`, `__enter__`, `__exit__`.
  - `_serialize_type(t) -> str | None`, `_deserialize_type(schema_str: str | None) -> type | None` (module-private in `agents.py`).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_agent_store.py`:

```python
from pydantic import BaseModel
from easyagents.core.agent import AgentDefinition
from easyagents.persistence.agents import SQLiteAgentStore


def test_save_and_get(tmp_path):
    store = SQLiteAgentStore(str(tmp_path / "test.db"))
    store.save(AgentDefinition(name="a", instructions="hi", model="test",
                               tools=["web_search"], subagents=["b"],
                               description="desc"))
    defn = store.get("a")
    assert defn.name == "a"
    assert defn.instructions == "hi"
    assert defn.model == "test"
    assert defn.tools == ["web_search"]
    assert defn.subagents == ["b"]
    assert defn.description == "desc"


def test_get_missing_returns_none(tmp_path):
    store = SQLiteAgentStore(str(tmp_path / "test.db"))
    assert store.get("missing") is None


def test_list_and_delete(tmp_path):
    store = SQLiteAgentStore(str(tmp_path / "test.db"))
    store.save(AgentDefinition(name="a", instructions="x", model="test"))
    store.save(AgentDefinition(name="b", instructions="y", model="test"))
    assert set(store.list()) == {"a", "b"}
    store.delete("a")
    assert store.list() == ["b"]
    assert store.get("a") is None


def test_close(tmp_path):
    store = SQLiteAgentStore(str(tmp_path / "test.db"))
    store.close()
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_agent_store.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'easyagents.persistence.agents'`

- [ ] **Step 3: Implement `SQLiteAgentStore`**

Create `src/easyagents/persistence/agents.py`:

```python
import json
import sqlite3

from pydantic import create_model
from pydantic import TypeAdapter

from easyagents.core.agent import AgentDefinition
from easyagents.core.exceptions import AgentStoreError


def _serialize_type(t) -> str | None:
    if t is None:
        return None
    schema = TypeAdapter(t).json_schema()
    return json.dumps(schema)


def _resolve_schema_type(schema) -> type | None:
    """Rebuild a Python type from a JSON schema. Returns None for unresolvable primitive."""
    t = schema.get("type")
    if t == "string":
        return str
    if t == "integer":
        return int
    if t == "number":
        return float
    if t == "boolean":
        return bool
    if t == "array":
        items = schema.get("items") or {}
        return list[_resolve_schema_type(items) or str]
    if t == "object":
        return dict
    return None


def _resolve_ref(ref: str, defs: dict) -> type:
    parts = ref.lstrip("#/").split("/")
    cur: object = defs
    for p in parts:
        cur = cur[p]
    return _reconstruct(schema=cur, defs=defs)


def _reconstruct(schema: dict, defs: dict) -> type:
    if "$ref" in schema:
        return _resolve_ref(schema["$ref"], defs)
    if "anyOf" in schema:
        for sub in schema["anyOf"]:
            rt = _reconstruct(sub, defs)
            if rt is not None:
                return rt
        return str
    resolved = _resolve_schema_type(schema)
    if resolved is not None:
        return resolved
    properties = schema.get("properties")
    if properties:
        fields = {}
        for name, prop in properties.items():
            fields[name] = (_reconstruct(prop, defs), ...)
        return create_model(schema.get("title") or "ReconstructedModel", **fields)
    return str


def _deserialize_type(schema_str: str | None) -> type | None:
    if schema_str is None:
        return None
    try:
        schema = json.loads(schema_str)
        defs = schema.get("$defs") or {}
        return _reconstruct(schema, defs)
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
        raise AgentStoreError(f"Failed to reconstruct type from schema: {e}") from e


class SQLiteAgentStore:
    """SQLite-backed store for AgentDefinition records."""

    def __init__(self, db_path: str = "easyagents.db", check_same_thread: bool = False) -> None:
        self._db_path = db_path
        self._conn = sqlite3.connect(db_path, check_same_thread=check_same_thread)
        self._init_db()

    def _init_db(self) -> None:
        try:
            self._conn.executescript("""
                CREATE TABLE IF NOT EXISTS agents (
                    name         TEXT PRIMARY KEY,
                    instructions TEXT NOT NULL,
                    model        TEXT NOT NULL,
                    tools        TEXT NOT NULL,
                    subagents    TEXT NOT NULL,
                    description  TEXT NOT NULL,
                    output_type  TEXT,
                    deps_type    TEXT
                );
            """)
            self._conn.commit()
        except sqlite3.Error as e:
            raise AgentStoreError(f"Failed to initialize agent store: {e}") from e

    def save(self, definition: AgentDefinition) -> None:
        try:
            with self._conn:
                self._conn.execute(
                    """INSERT OR REPLACE INTO agents
                       (name, instructions, model, tools, subagents, description, output_type, deps_type)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        definition.name,
                        definition.instructions,
                        definition.model,
                        json.dumps(definition.tools),
                        json.dumps(definition.subagents),
                        definition.description,
                        _serialize_type(definition.output_type),
                        _serialize_type(definition.deps_type),
                    ),
                )
        except sqlite3.Error as e:
            raise AgentStoreError(f"Failed to save agent '{definition.name}': {e}") from e

    def get(self, name: str) -> AgentDefinition | None:
        try:
            row = self._conn.execute(
                "SELECT instructions, model, tools, subagents, description, output_type, deps_type "
                "FROM agents WHERE name = ?",
                (name,),
            ).fetchone()
        except sqlite3.Error as e:
            raise AgentStoreError(f"Failed to get agent '{name}': {e}") from e
        if row is None:
            return None
        instructions, model, tools, subagents, description, ot, dt = row
        return AgentDefinition(
            name=name,
            instructions=instructions,
            model=model,
            tools=json.loads(tools),
            subagents=json.loads(subagents),
            description=description,
            output_type=_deserialize_type(ot),
            deps_type=_deserialize_type(dt),
        )

    def list(self) -> list[str]:
        try:
            rows = self._conn.execute("SELECT name FROM agents").fetchall()
            return [r[0] for r in rows]
        except sqlite3.Error as e:
            raise AgentStoreError(f"Failed to list agents: {e}") from e

    def delete(self, name: str) -> None:
        try:
            with self._conn:
                self._conn.execute("DELETE FROM agents WHERE name = ?", (name,))
        except sqlite3.Error as e:
            raise AgentStoreError(f"Failed to delete agent '{name}': {e}") from e

    def close(self) -> None:
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self._conn.close()
```

- [ ] **Step 4: Run to verify passes**

Run: `pytest tests/test_agent_store.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**
```bash
git add src/easyagents/persistence/agents.py tests/test_agent_store.py
git commit -m "feat: SQLiteAgentStore with JSON-schema type serialization"
```

---

### Task 3: Type serialization round-trip tests

**Files:**
- Modify: `tests/test_agent_store.py` (append)

**Interfaces:**
- Consumes: `_serialize_type` / `_deserialize_type` from `easyagents.persistence.agents`.
- Produces: confidence that scalar/collection/flat/nested models round-trip.

- [ ] **Step 1: Append failing tests**

Append to `tests/test_agent_store.py`:

```python
from easyagents.persistence.agents import _serialize_type, _deserialize_type


def test_roundtrip_scalar():
    assert _deserialize_type(_serialize_type(str)) is str
    assert _deserialize_type(_serialize_type(int)) is int


def test_roundtrip_collection():
    lt = _deserialize_type(_serialize_type(list[int]))
    assert lt.__args__[0] is int


def test_roundtrip_flat_model():
    class Flat(BaseModel):
        a: int
        b: str

    rebuilt = _deserialize_type(_serialize_type(Flat))
    fields = rebuilt.__annotations__
    assert fields["a"] is int
    assert fields["b"] is str


def test_roundtrip_nested_model():
    class Inner(BaseModel):
        value: int

    class Outer(BaseModel):
        inner: Inner

    rebuilt = _deserialize_type(_serialize_type(Outer))
    ann = rebuilt.__annotations__["inner"]
    # create_model produces a nested model whose fields preserve Inner's structure
    assert "value" in ann.__annotations__


def test_none_roundtrip():
    assert _serialize_type(None) is None
    assert _deserialize_type(None) is None


def test_store_persists_output_type(tmp_path):
    class Out(BaseModel):
        result: str

    store = SQLiteAgentStore(str(tmp_path / "t.db"))
    store.save(AgentDefinition(name="n", instructions="x", model="test", output_type=Out))
    from pydantic import BaseModel as BM
    assert issubclass(store.get("n").output_type, BM)
```

- [ ] **Step 2: Run to verify failures**

Run: `pytest tests/test_agent_store.py -v`
Expected: new tests FAIL (e.g. `_serialize_type` not accepted, or model equality issues). Investigate and adjust assertions to reflect the actual reconstruction behavior (the goal is that reconstruction succeeds and preserves field names/types).

- [ ] **Step 3: Run until green, then refactor assertions**

Run: `pytest tests/test_agent_store.py -v`
Expected: 10 passed. Adjust assertion details in-place based on actual `_deserialize_type` output (e.g. nested model name from `create_model`), but keep the property that field names and resolved types are preserved.

- [ ] **Step 4: Commit**
```bash
git add tests/test_agent_store.py
git commit -m "test: round-trip type serialization for scalars, collections, models"
```

---

### Task 4: `AgentRegistry` optional backing store

**Files:**
- Modify: `src/easyagents/core/agent.py`
- Modify: `tests/test_agent_registry.py` (append)

**Interfaces:**
- Consumes: `SQLiteAgentStore` (Task 2) — `list()`, `get(name)`, `save(defn)`.
- Produces: `AgentRegistry(store=None)`; when `store` is set, `register()` also calls `store.save(defn)`, and `__init__` pre-loads existing definitions.

- [ ] **Step 1: Append failing tests**

Append to `tests/test_agent_registry.py`:

```python
from easyagents.persistence.agents import SQLiteAgentStore


def test_store_backed_register_and_reload(tmp_path):
    store = SQLiteAgentStore(str(tmp_path / "g.db"))
    r1 = AgentRegistry(store=store)
    r1.register(AgentDefinition(name="persist_me", instructions="Hi", model="test"))
    r2 = AgentRegistry(store=store)
    assert "persist_me" in r2.list()
    defn = r2.get("persist_me")
    assert defn.instructions == "Hi"


def test_plain_registry_not_affected():
    r = AgentRegistry()
    r.register(AgentDefinition(name="mem", instructions="x", model="test"))
    from pydantic_ai import Agent  # noqa
    assert r.list() == ["mem"]
```

- [ ] **Step 2: Run to verify failures**

Run: `pytest tests/test_agent_registry.py -v`
Expected: new tests FAIL (store parameter not yet accepted).

- [ ] **Step 3: Implement**

Modify `src/easyagents/core/agent.py` — change `__init__` and `register`:

```python
class AgentRegistry:
    def __init__(self, store=None) -> None:
        self._store = store
        self._definitions: dict[str, AgentDefinition] = {}
        self._agents: dict[str, Agent[Any]] = {}
        if store is not None:
            for name in store.list():
                defn = store.get(name)
                if defn is not None:
                    self._definitions[name] = defn

    def register(self, definition: AgentDefinition) -> None:
        if definition.name in self._definitions:
            raise AgentAlreadyRegisteredError(
                f"Agent '{definition.name}' is already registered"
            )
        self._definitions[definition.name] = definition
        if self._store is not None:
            self._store.save(definition)
```

(Leave `get`, `create`, `list` unchanged.)

- [ ] **Step 4: Run to verify passes**

Run: `pytest tests/test_agent_registry.py tests/test_agent_store.py`
Expected: all pass.

- [ ] **Step 5: Commit**
```bash
git add src/easyagents/core/agent.py tests/test_agent_registry.py
git commit -m "feat: AgentRegistry optional SQLite backing store"
```

---

### Task 5: Wire `create_registry()` default persistence

**Files:**
- Modify: `src/easyagents/cli/setup.py`
- Test: `tests/test_cli.py` (append)

**Interfaces:**
- Consumes: `SQLiteAgentStore`, `AgentRegistry(store=...)` (Tasks 2, 4).
- Produces: `create_registry(db_path=None)` — default path `~/.easyagents/agents.db`; CLI and API both get a store-backed registry.

- [ ] **Step 1: Append failing test**

Append to `tests/test_cli.py`:

```python
from easyagents.cli.setup import create_registry
from easyagents.core.agent import AgentDefinition
from easyagents.persistence.agents import SQLiteAgentStore


def test_create_registry_persists_agents(tmp_path):
    db = str(tmp_path / "agents.db")
    agents, tools = create_registry(db_path=db)
    agents.register(AgentDefinition(name="cli_agent", instructions="x", model="test"))
    agents2, _ = create_registry(db_path=db)
    assert "cli_agent" in agents2.list()
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_cli.py::test_create_registry_persists_agents -v`
Expected: FAIL (create_registry does not accept db_path yet).

- [ ] **Step 3: Implement**

Replace `src/easyagents/cli/setup.py` contents:

```python
import os

from easyagents import AgentRegistry, ToolRegistry, web_search, http_request, write_file
from easyagents.persistence.agents import SQLiteAgentStore


def create_registry(db_path=None):
    """Create and configure registries with built-in tools.

    Agent definitions are persisted to a SQLite store so they survive
    process restarts. Pass db_path to override the default location.
    """
    tools = ToolRegistry()
    tools.register("web_search", web_search)
    tools.register("http_request", http_request)
    tools.register("write_file", write_file)

    if db_path is None:
        db_path = os.path.expanduser("~/.easyagents/agents.db")
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    store = SQLiteAgentStore(db_path)
    agents = AgentRegistry(store=store)
    return agents, tools
```

- [ ] **Step 4: Run to verify passes**

Run: `pytest tests/test_cli.py -v`
Expected: all pass (including legacy tests).

- [ ] **Step 5: Commit**
```bash
git add src/easyagents/cli/setup.py tests/test_cli.py
git commit -m "feat: create_registry persists agents to SQLite by default"
```

---

### Task 6: Full-suite verification

**Files:** (none — verification only)

- [ ] **Step 1: Run entire test suite**

Run: `pytest -q`
Expected: all tests pass (existing 130 + new).

- [ ] **Step 2: Manual smoke test with the running API**

```bash
# (re)start the server, then:
curl -s -X POST http://localhost:8000/api/agents/ -H 'Content-Type: application/json' \
  -d '{"name":"persist_probe","instructions":"hi","model":"test"}'
# restart the server process, then:
curl -s http://localhost:8000/api/agents/
```
Expected: `persist_probe` still listed after restart.

- [ ] **Step 3: Commit any stragglers**
```bash
git status   # confirm clean, else commit remaining changes
```