from pydantic import BaseModel, field_validator


class AgentCreateRequest(BaseModel):
    name: str
    instructions: str
    model: str = "test"
    tools: list[str] = []
    subagents: list[str] = []
    description: str = ""

    @field_validator("tools", "subagents", mode="before")
    @classmethod
    def empty_list(cls, v):
        if v in (None, ""):
            return []
        if isinstance(v, str):
            return [s.strip() for s in v.split(",") if s.strip()]
        return v


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
