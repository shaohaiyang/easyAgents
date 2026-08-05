# EasyAgents

通用多智能体研究工作台 SDK，基于 [Pydantic AI](https://ai.pydantic.dev/) 构建。提供智能体注册、编排、会话管理、持久化、工具、工作流（含人工审批）、CLI、REST API 与 Web 界面。

## 特性

- **智能体定义与注册**：声明式 `AgentDefinition`，支持工具绑定与子智能体。
- **编排模式**：`OrchestratorWorker`（并行分解）、`DynamicOrchestrator`（LLM 动态分解）、`HandoffPattern`（智能体交接）、`RouterPattern`（LLM 路由）。
- **图工作流 + 人工审批**：`GraphWorkflow` 支持 HITL 暂停 / 恢复，`CheckpointManager` 内存与 SQLite 断点持久化。
- **会话管理**：`SessionStore` 抽象，内置 `InMemorySessionStore` / `SQLiteSessionStore`。
- **上下文管理**：`ContextManager` 阈值触发 LLM 压缩，防止上下文溢出。
- **内置工具**：`web_search`、`http_request`、`write_file`（含路径安全校验）。
- **可观测性**：`configure()` 一键接入 Logfire 跟踪。
- **四种使用形态**：Python SDK / Typer CLI / FastAPI REST API / Web UI。

## 安装

```bash
pip install "easyagents[dev]"
# 或从源码：
uv sync --extra dev
```

依赖：Python 3.11+，Pydantic AI ≥0.0.30，Pydantic v2，Logfire，duckduckgo-search，httpx，typer，fastapi，uvicorn。

## 快速开始

> 默认模型为 `"test"`（`TestModel`），本地可运行，无需真实 LLM API。

```python
from pydantic import BaseModel
from pydantic_ai.models.test import TestModel
from easyagents import (
    AgentDefinition, AgentRegistry, SessionManager, ToolRegistry, configure,
)

configure(service_name="easyagents-demo")

class ResearchFindings(BaseModel):
    products: list[str]
    summary: str

tools = ToolRegistry()
tools.register("web_search", lambda q: [{"title": "AirPods Pro 2", "url": "https://apple.com"}])

agents = AgentRegistry()
agents.register(AgentDefinition(
    name="researcher",
    instructions="Research products using web_search.",
    model="test",
    tools=["web_search"],
    output_type=ResearchFindings,
))
agents.register(AgentDefinition(
    name="orchestrator",
    instructions="Use delegate_researcher to research, then summarize.",
    model="test",
    subagents=["researcher"],
))

session_mgr = SessionManager()
session = session_mgr.create()

agent = agents.create("orchestrator", tools)
result = agent.run_sync("调研最近爆火的蓝牙耳机", model=TestModel(
    custom_output_text=str(ResearchFindings(products=["AirPods Pro 2"], summary="Top competitor.")),
))
session_mgr.save_messages(session.conversation_id, result.all_messages())
print(result.output, result.usage)
```

完整可运行示例见 [`scripts/demo.py`](scripts/demo.py)。

## 编排模式

```python
import asyncio
from easyagents import OrchestratorWorker, SubtaskTemplate, HandoffPattern, RouterPattern

# 并行子任务编排
orch = OrchestratorWorker(
    orchestrator_agent="coordinator",
    subtasks=[SubtaskTemplate(agent="researcher", task_template="调研{topic}")],
    registry=agents, tool_registry=tools,
)
result = asyncio.run(orch.run("蓝牙耳机", params={}, model="test"))

# 智能体交接
handoff = HandoffPattern(registry=agents, tool_registry=tools, model="test")
hdr = asyncio.run(handoff.run(agents=["researcher", "writer"], user_input="写文章"))

# LLM 路由
router = RouterPattern(agents=agents.list(), registry=agents, tool_registry=tools, model="test")
best = asyncio.run(router.route("查一下市场数据"))
```

## 图工作流与人工审批

```python
from easyagents import GraphWorkflow, AgentNode, ApprovalNode

wf = GraphWorkflow(decomposition={
    "step1": AgentNode("researcher"),
    "step2": ApprovalNode("reviewer"),
})
plan = wf.build_plan()              # 构建并暂停在待审批节点
for p in plan.pending:              # 手动审批
    p.approve()
result = wf.resume(plan)            # 恢复执行
```

## CLI

```bash
easyagents run researcher --prompt "调研蓝牙耳机"
easyagents agents
easyagents sessions
easyagents session-show <conversation_id>
easyagents orchestrate "调研蓝牙耳机"
easyagents route "查一下市场数据"
easyagents serve --port 8000       # 启动 REST API + Web UI
```

## REST API & Web UI

启动服务：

```bash
easyagents serve --port 8000
```

- Web UI：`http://localhost:8000/web`（Agents / Sessions / Patterns / Approvals 四个标签页）
- REST API（`/api` 前缀）：

| 路由 | 方法 | 说明 |
|------|------|------|
| `/api/agents` | GET/POST | 列出 / 注册智能体 |
| `/api/sessions` | GET/POST | 会话列表 / 新建会话 |
| `/api/sessions/{id}` | GET/POST | 会话详情 / 运行 |
| `/api/patterns/orchestrate` | POST | 编排 |
| `/api/patterns/handoff` | POST | 交接 |
| `/api/patterns/route` | POST | 路由 |
| `/api/approvals` | GET/POST | 待审批 / 处理审批 |
| `/api/checkpoints` | GET/POST/PUT | 断点管理 |

交互式文档访问 `http://localhost:8000/docs`。

## 公开 API

`easyagents` 顶层导出（`__all__`，44 个符号）：

- **核心**：`AgentDefinition`、`AgentRegistry`、`Session`、`SessionManager`
- **工具**：`ToolRegistry`、`ToolMetadata`、`web_search`、`http_request`、`write_file`
- **持久化**：`SessionStore`、`InMemorySessionStore`、`SQLiteSessionStore`
- **上下文**：`ContextManager`
- **编排**：`OrchestratorWorker`、`SubtaskTemplate`、`OrchestrationResult`、`DynamicOrchestrator`、`DynamicSubtask`
- **模式**：`HandoffPattern`、`HandoffResult`、`RouterPattern`
- **工作流**：`AgentNode`、`ApprovalNode`、`GraphWorkflow`、`GraphResult`、`PendingApproval`、`ApprovalResult`、`CheckpointManager`、`Checkpoint`
- **可观测性**：`configure`
- **异常**：`EasyAgentsError` 及 14 个子类（`AgentAlreadyRegisteredError`、`SessionStoreError`、`OrchestrationError`、`HandoffError`、`RoutingError`、`WorkflowError`、`CheckpointError`、`ApprovalError` 等）

## 架构

```
easyagents
├── core/          AgentDefinition / AgentRegistry / SessionManager / exceptions
├── persistence/   SessionStore 抽象（InMemory / SQLite / base）
├── context/       ContextManager 上下文压缩
├── patterns/      Orchestrator / DynamicOrchestrator / Handoff / Router / Delegation
├── workflows/     GraphWorkflow / AgentNode / ApprovalNode / CheckpointManager
├── tools/         ToolRegistry + builtin（web_search / http_request / write_file）
├── observability/ Logfire 跟踪
├── api/           FastAPI（agents/sessions/patterns/approvals/checkpoints 路由）
├── cli/           Typer CLI
└── web/           static HTML/CSS/JS Web UI
```

## 测试

```bash
pytest            # 128 个测试，全部使用 FunctionModel/TestModel，无真实 LLM 调用
```

## 设计文档

各阶段设计与实现计划见 [docs/superpowers/specs](docs/superpowers/specs/) 与 [docs/superpowers/plans](docs/superpowers/plans/)：

- MVP → Phase 1.5（SQLite / 上下文 / 工具）→ Phase 2（编排 / 交接 / 路由）→ Phase 3（图工作流 / HITL / 断点）→ Phase 4（CLI / REST API）→ Phase 5（Web UI）