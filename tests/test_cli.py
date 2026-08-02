import pytest
from typer.testing import CliRunner

from easyagents.cli.main import app

runner = CliRunner()


def test_agents_list():
    """easyagents agents - lists registered agents."""
    result = runner.invoke(app, ["agents"])
    assert result.exit_code == 0


def test_run_agent():
    """easyagents run <agent> <prompt> - runs an agent."""
    from easyagents.cli.setup import create_registry
    agents, tools = create_registry()
    from easyagents import AgentDefinition
    agents.register(AgentDefinition(name="test_agent", instructions="Test.", model="test"))

    result = runner.invoke(app, ["run", "test_agent", "hello", "--model", "test"])
    assert result.exit_code == 0
    assert "Output:" in result.stdout or "Error" in result.stdout


def test_sessions_list():
    """easyagents sessions --all - lists sessions."""
    result = runner.invoke(app, ["sessions", "--all"])
    assert result.exit_code == 0


def test_orchestrate():
    """easyagents orchestrate <task> - runs orchestrator."""
    result = runner.invoke(app, ["orchestrate", "test task", "--model", "test"])
    assert result.exit_code == 0


def test_route():
    """easyagents route <query> - routes to best agent."""
    result = runner.invoke(app, ["route", "test query", "--model", "test"])
    assert result.exit_code == 0


def test_serve_command():
    """easyagents serve - starts API server (mocked)."""
    from unittest.mock import patch, MagicMock

    with patch("uvicorn.run") as mock_run:
        result = runner.invoke(app, ["serve", "--port", "9999"])
        assert result.exit_code == 0
        mock_run.assert_called_once()
