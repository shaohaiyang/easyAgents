from fastapi import APIRouter, HTTPException
from easyagents.api.models import OrchestrateRequest, HandoffRequest, RouteRequest
from easyagents.cli.setup import create_registry
from easyagents.core.agent import AgentDefinition
from easyagents import OrchestratorWorker, SubtaskTemplate, HandoffPattern, RouterPattern

router = APIRouter()
_registry, _tools = create_registry()

for _name, _instr in [
    ("researcher", "Research information."),
    ("coder", "Write and debug code."),
    ("writer", "Write documentation and reports."),
]:
    try:
        _registry.register(AgentDefinition(name=_name, instructions=_instr, model="test"))
    except Exception:
        pass


@router.post("/route")
async def route_pattern(req: RouteRequest):
    agents = _registry.list()
    if not agents:
        return {"agent": None}
    router_pattern = RouterPattern(
        agents=agents,
        registry=_registry,
        tool_registry=_tools,
        model=req.model or "test",
    )
    try:
        agent_name = await router_pattern.route(req.user_input)
        return {"agent": agent_name}
    except Exception:
        return {"agent": agents[0]}


@router.post("/orchestrate")
async def orchestrate_pattern(req: OrchestrateRequest):
    agents = _registry.list()
    if not agents:
        return {"output": "", "subtask_count": 0}
    subtasks = [SubtaskTemplate(agent=n, task_template=req.task) for n in agents[:2]]
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
