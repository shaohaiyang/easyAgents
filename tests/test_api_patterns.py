import pytest
from fastapi.testclient import TestClient
from easyagents.api.app import app

client = TestClient(app)


def test_route_pattern():
    response = client.post("/api/patterns/route", json={
        "user_input": "test query",
        "model": "test",
    })
    assert response.status_code == 200


def test_orchestrate_pattern():
    response = client.post("/api/patterns/orchestrate", json={
        "task": "test task",
        "params": {},
        "model": "test",
    })
    assert response.status_code == 200


def test_handoff_pattern():
    response = client.post("/api/patterns/handoff", json={
        "agents": [],
        "user_input": "test",
        "model": "test",
    })
    assert response.status_code == 200
