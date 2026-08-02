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
