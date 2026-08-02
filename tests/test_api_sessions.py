import pytest
from fastapi.testclient import TestClient
from easyagents.api.app import app

client = TestClient(app)


def test_create_session():
    response = client.post("/api/sessions")
    assert response.status_code == 201
    assert "conversation_id" in response.json()


def test_list_sessions():
    client.post("/api/sessions")
    response = client.get("/api/sessions")
    assert response.status_code == 200
    assert "sessions" in response.json()


def test_get_session():
    create = client.post("/api/sessions")
    cid = create.json()["conversation_id"]
    response = client.get(f"/api/sessions/{cid}")
    assert response.status_code == 200
    assert response.json()["conversation_id"] == cid


def test_get_nonexistent_returns_404():
    response = client.get("/api/sessions/nonexistent")
    assert response.status_code == 404


def test_delete_session():
    create = client.post("/api/sessions")
    cid = create.json()["conversation_id"]
    response = client.delete(f"/api/sessions/{cid}")
    assert response.status_code == 204
