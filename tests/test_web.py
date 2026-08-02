from fastapi.testclient import TestClient
from easyagents.api.app import app

client = TestClient(app)


def test_root_redirects_to_web():
    response = client.get("/", follow_redirects=False)
    assert response.status_code in (302, 307)


def test_web_index_html():
    response = client.get("/web/index.html")
    assert response.status_code == 200
    assert "EasyAgents" in response.text


def test_web_static_files():
    response = client.get("/web/style.css")
    assert response.status_code == 200
    response = client.get("/web/app.js")
    assert response.status_code == 200
