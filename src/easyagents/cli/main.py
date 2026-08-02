import typer

from easyagents.cli.setup import create_registry

app = typer.Typer(name="easyagents", help="EasyAgents multi-agent workbench CLI")


@app.command()
def run(agent: str, prompt: str, model: str = "test"):
    """Run an agent with a prompt."""
    agents, tools = create_registry()
    try:
        agent_obj = agents.create(agent, tools)
        result = agent_obj.run_sync(prompt, model=model)
        typer.echo(f"Output: {result.output}")
        typer.echo(f"Usage: {result.usage}")
    except Exception as e:
        typer.echo(f"Error: {e}")


@app.command()
def agents():
    """List registered agents."""
    registry, _ = create_registry()
    names = registry.list()
    if not names:
        typer.echo("No agents registered.")
    for name in names:
        typer.echo(name)


@app.command()
def sessions(list_all: bool = typer.Option(False, "--all", help="List all sessions")):
    """List sessions."""
    import os

    from easyagents import SessionManager, SQLiteSessionStore

    db_path = os.path.expanduser("~/.easyagents/sessions.db")
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    mgr = SessionManager(SQLiteSessionStore(db_path))
    ids = mgr.list_sessions()
    if not ids:
        typer.echo("No sessions.")
    for sid in ids:
        typer.echo(sid)


@app.command(name="session-show")
def session_show(conversation_id: str):
    """Show session messages."""
    import os

    from easyagents import SessionManager, SQLiteSessionStore

    db_path = os.path.expanduser("~/.easyagents/sessions.db")
    mgr = SessionManager(SQLiteSessionStore(db_path))
    session = mgr.get(conversation_id)
    if not session:
        typer.echo(f"Session '{conversation_id}' not found.", err=True)
        raise typer.Exit(1)
    typer.echo(f"Session: {session.conversation_id}")
    typer.echo(f"Messages: {len(session.messages)}")


@app.command()
def orchestrate(task: str, model: str = "test"):
    """Run OrchestratorWorker on a task."""
    agents, tools = create_registry()
    from easyagents import OrchestratorWorker, SubtaskTemplate

    if not agents.list():
        typer.echo("No agents registered.")
        return
    subtasks = [
        SubtaskTemplate(agent=name, task_template=task)
        for name in agents.list()[:2]
    ]
    orch = OrchestratorWorker(
        orchestrator_agent="coordinator",
        subtasks=subtasks,
        registry=agents,
        tool_registry=tools,
    )
    import asyncio

    try:
        result = asyncio.run(
            orch.run(task, params={}, model=None if model == "test" else model)
        )
        typer.echo(f"Output: {result.output}")
    except Exception as e:
        typer.echo(f"Error: {e}")


@app.command()
def route(query: str, model: str = "test"):
    """Route to best agent via RouterPattern."""
    agents, tools = create_registry()
    if not agents.list():
        typer.echo("No agents registered.")
        return
    from easyagents import RouterPattern

    router = RouterPattern(
        agents=agents.list(),
        registry=agents,
        tool_registry=tools,
        model=model,
    )
    import asyncio

    try:
        agent_name = asyncio.run(router.route(query))
        typer.echo(f"Routed to: {agent_name}")
    except Exception as e:
        typer.echo(f"Routing error: {e}")


@app.command()
def serve(port: int = 8000):
    """Start FastAPI server."""
    import uvicorn

    typer.echo(f"Starting EasyAgents API on port {port}...")
    uvicorn.run("easyagents.api.app:app", host="0.0.0.0", port=port)


if __name__ == "__main__":
    app()
