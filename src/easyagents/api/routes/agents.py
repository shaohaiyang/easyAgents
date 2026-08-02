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
