from fastapi.testclient import TestClient
from easyagents.api.app import app

client = TestClient(app)


def test_get_pending_approval():
    response = client.get("/api/approvals/wf-1")
    assert response.status_code == 200
    assert "workflow_id" in response.json()


def test_submit_approval():
    response = client.post("/api/approvals/wf-1", json={
        "approved": True,
        "feedback": "Looks good",
    })
    assert response.status_code == 200
    assert "status" in response.json()
