import os

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from easyagents.api.routes import agents, sessions, patterns, approvals, checkpoints

app = FastAPI(title="EasyAgents Workbench", version="0.1.0")
app.include_router(agents.router, prefix="/api/agents", tags=["agents"])
app.include_router(sessions.router, prefix="/api/sessions", tags=["sessions"])
app.include_router(patterns.router, prefix="/api/patterns", tags=["patterns"])
app.include_router(approvals.router, prefix="/api/approvals", tags=["approvals"])
app.include_router(checkpoints.router, prefix="/api/checkpoints", tags=["checkpoints"])

web_dir = os.path.join(os.path.dirname(__file__), "..", "web", "static")
app.mount("/web", StaticFiles(directory=web_dir), name="web")


@app.get("/")
async def root_redirect():
    return RedirectResponse(url="/web/index.html")
