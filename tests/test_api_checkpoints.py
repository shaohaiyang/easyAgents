from fastapi.testclient import TestClient
from easyagents.api.app import app

client = TestClient(app)


def test_list_checkpoints():
    response = client.get("/api/checkpoints/wf-1")
    assert response.status_code == 200
    assert "checkpoints" in response.json()


def test_rollback():
    response = client.post("/api/checkpoints/rollback", json={
        "checkpoint_id": "fake-id",
    })
    assert response.status_code == 200
