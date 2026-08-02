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
