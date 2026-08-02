from fastapi import FastAPI
from easyagents.api.routes import agents, sessions

app = FastAPI(title="EasyAgents Workbench", version="0.1.0")
app.include_router(agents.router, prefix="/api/agents", tags=["agents"])
app.include_router(sessions.router, prefix="/api/sessions", tags=["sessions"])


@app.get("/")
async def root():
    return {"name": "EasyAgents Workbench", "version": "0.1.0"}
