# EasyAgents Agent SQLite 持久化 设计

日期：2026-08-05
状态：已批准

## 背景与目标

当前 `AgentRegistry` 是纯内存存储（`dict[AgentDefinition]`），Web UI / API 注册的智能体在服务器重启后全部丢失。本设计为目标：让 agent 定义持久化到 SQLite，服务重启后自动恢复，覆盖 CLI 与 API 两条使用路径。

## 约束与取舍

- **持久化字段**：`AgentDefinition` 中 6 个 JSON 可序列化字段全部持久化：`name`、`instructions`、`model`、`tools`、`subagents`、`description`。
- **类型字段**：`output_type` / `deps_type` 是 Python 类型对象（多为 Pydantic model），不能直接入 DB。**方案：仅存其 JSON schema，重载时用 `pydantic.create_model` 可逆重建**（用户已确认）。
- **向后兼容**：`AgentRegistry()` 不传 store 时维持纯内存行为，现有 130 个测试与已有用户代码不受影响。
- **默认自动启用**：`create_registry()` 默认给 `AgentRegistry` 接上 SQLite 存储（用户已确认），CLI 与 API 重启不丢 agent。

## 架构

新增 `persistence/agents.py`，遵循现有 `persistence/sqlite.py`（`SQLiteSessionStore`）风格：持久单连接、`check_same_thread=False`、`with self._conn` 事务、`PRAGMA foreign_keys = ON`。

```
persistence/agents.py    →  SQLiteAgentStore + 类型序列化工具（私有）
core/agent.py            →  AgentRegistry 支持可选 backing store
cli/setup.py             →  create_registry() 默认接上 SQLite 存储
api/routes/agents.py     →  复用 create_registry()，无改动
```

### 组件一：`SQLiteAgentStore`

构造：`SQLiteAgentStore(db_path="easyagents.db", check_same_thread=False)`

建表：

```sql
CREATE TABLE IF NOT EXISTS agents (
    name         TEXT PRIMARY KEY,
    instructions TEXT NOT NULL,
    model        TEXT NOT NULL,
    tools        TEXT NOT NULL,   -- JSON 数组
    subagents    TEXT NOT NULL,   -- JSON 数组
    description  TEXT NOT NULL,
    output_type  TEXT,            -- JSON schema or NULL
    deps_type    TEXT             -- JSON schema or NULL
);
```

方法：
- `save(definition: AgentDefinition) -> None`：UPSERT 或 INSERT，`output_type`/`deps_type` 经 `_serialize_type` 转 JSON schema。
- `get(name: str) -> AgentDefinition | None`：读取并 `_deserialize_type` 还原类型。
- `list() -> list[str]`：返回所有 name。
- `delete(name: str) -> None`：删除。
- `close() -> None`、`__enter__`/`__exit__`。

### 组件二：类型序列化工具（私有函数）

`_serialize_type(t) -> str | None`：
- `t is None` → 返回 `None`。
- 否则 `pydantic.TypeAdapter(t).json_schema()` 转为 JSON 字符串存储。

`_deserialize_type(schema_json: str | None) -> type | None`：
- `None` → 返回 `None`。
- 解析 schema，按 `"type"` 映射回内置类型：
  - `string` → `str`；`integer` → `int`；`number` → `float`；`boolean` → `bool`；`array` → `list`；`object` 无 `properties` → `dict`；`null`（nullable via `anyOf`）→ 递归取首个非空分支。
- `object` 含 `properties`（Pydantic model）→ 用 `pydantic.create_model` 递归重建：每个字段从 `properties` 递归解析类型（含 `items`、`anyOf`、`$ref`/`$defs` 解析为嵌套 model）。

设计诚实性：支持 `str`/`int`/`float`/`bool`/`list[...]`/`dict`/扁平 model/嵌套 `$defs` model。重建后的 model 保留字段与类型，但不含原类的自定义方法/校验器（记录为已知限制）。

### 组件三：`AgentRegistry` 扩展

```python
class AgentRegistry:
    def __init__(self, store=None) -> None:
        self._store = store
        self._definitions = {}
        self._agents = {}
        if store is not None:
            for name in store.list():
                defn = store.get(name)
                if defn is not None:
                    self._definitions[name] = defn
```

- `register(definition)`：现有逻辑不变，`self._definitions` 写入后，若 `self._store` 存在则 `self._store.save(definition)`。
- 其余方法（`get`/`create`/`list`）不变。

### 组件四：`create_registry()` 接线

```python
def create_registry(db_path=None):
    tools = ToolRegistry()
    tools.register("web_search", web_search)
    tools.register("http_request", http_request)
    tools.register("write_file", write_file)
    db_path = db_path or os.path.expanduser("~/.easyagents/agents.db")
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    store = SQLiteAgentStore(db_path)
    agents = AgentRegistry(store=store)
    return agents, tools
```

说明：`create_registry` 创建的 store 生命周期跟随服务进程（CLI 命令即用即弃，API 常驻存活）。

## 错误处理

- SQLite 操作失败 → 复用 `SessionStoreError` 或新增 `AgentStoreError`（`EasyAgentsError` 子类，保持一致性）。决定：新增 `AgentStoreError`，见「异常」。
- 类型无法可逆还原 → 抛 `AgentStoreError`（带清晰提示），不影响该 agent 的其余字段加载语义——但 store 层面失败应整体失败并明确报错（简单一致，避免部分加载导致隐性问题）。

## 异常

新增 `AgentStoreError(EasyAgentsError)`，加入 `src/easyagents/core/exceptions.py` 与 `__init__.py` 导出，并同步 README 公开 API 列表。

## 测试计划

新增测试文件 `tests/test_agent_store.py`：

1. `SQLiteAgentStore` 基础：save / get / list / delete（含不存在返回 `None`）、close 后重建连接。
2. 类型序列化往返：
   - `str`、`int`、`list[int]`、`dict[str, str]`
   - 扁平 Pydantic model（如 `class Foo(BaseModel): a: int`）
   - 嵌套 `$defs` model
3. `AgentRegistry(store=...)`：注册后新开同一 store 重载，agent 仍在、字段完整、`output_type` 还原后可 `create()`。
4. `create_registry()` 集成：注册 → 新建 store → agent 仍在。
5. 向后兼容：`AgentRegistry()`（无 store）行为不回归（现有测试已覆盖，新增断言注册不落盘）。

复用 `tmp_path` fixture 生成独立 DB，避免污染用户真实 `~/.easyagents`。

## 范围外（不做）

- agent 的已构造 `Agent` 实例不持久化（仅持久化定义，运行时按需 `create()`）。
- `output_type`/`deps_type` 的自定义方法/校验器不做持久化（已知限制）。
- 删除 agent 的 UI/API 入口（store 提供 `delete`，但不新增 HTTP 端点）。