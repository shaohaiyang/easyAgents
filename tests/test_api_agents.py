import pytest
from fastapi.testclient import TestClient
from easyagents.api.app import app

client = TestClient(app)


def test_list_agents():
    response = client.get("/api/agents")
    assert response.status_code == 200
    data = response.json()
    assert "agents" in data


def test_register_agent():
    response = client.post("/api/agents", json={
        "name": "test_bot",
        "instructions": "You are a test bot.",
        "model": "test",
    })
    assert response.status_code == 201
    assert "test_bot" in response.json()["name"]


def test_register_duplicate_returns_error():
    client.post("/api/agents", json={
        "name": "dup_bot",
        "instructions": "Dup.",
        "model": "test",
    })
    response = client.post("/api/agents", json={
        "name": "dup_bot",
        "instructions": "Dup.",
        "model": "test",
    })
    assert response.status_code == 400


def test_register_agent_with_empty_tools_and_subagents():
    response = client.post("/api/agents", json={
        "name": "empty_tools_bot",
        "instructions": "Test.",
        "model": "test",
        "tools": "",
        "subagents": "",
    })
    assert response.status_code == 201
    data = client.get("/api/agents").json()
    bot = next(a for a in data["agents"] if a["name"] == "empty_tools_bot")
    assert bot["tools"] == []
    assert bot["subagents"] == []


def test_register_agent_with_comma_separated_tools():
    response = client.post("/api/agents", json={
        "name": "csv_tools_bot",
        "instructions": "Test.",
        "model": "test",
        "tools": "web_search,http_request",
        "subagents": "researcher",
    })
    assert response.status_code == 201
    data = client.get("/api/agents").json()
    bot = next(a for a in data["agents"] if a["name"] == "csv_tools_bot")
    assert bot["tools"] == ["web_search", "http_request"]
    assert bot["subagents"] == ["researcher"]
