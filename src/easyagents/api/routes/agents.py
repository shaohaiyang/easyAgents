from fastapi import APIRouter, HTTPException
from easyagents.api.models import AgentCreateRequest
from easyagents.cli.setup import create_registry
from easyagents.core.agent import AgentDefinition
from easyagents.core.exceptions import AgentAlreadyRegisteredError

router = APIRouter()
_registry, _tools = create_registry()


@router.get("/")
async def list_agents():
    result = []
    for name in _registry.list():
        defn = _registry.get(name)
        result.append({
            "name": defn.name,
            "model": defn.model,
            "instructions": defn.instructions,
            "description": defn.description,
            "tools": defn.tools,
            "subagents": defn.subagents,
        })
    return {"agents": result}


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
