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
