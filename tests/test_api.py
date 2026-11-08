from fastapi.testclient import TestClient
from app.main import app

def test_health():
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

def test_checkout():
    with TestClient(app) as client:
        response = client.get("/checkout")
        assert response.status_code == 200
        assert response.json()["status"] == "completed"

def test_ai_is_simulated():
    with TestClient(app) as client:
        response = client.get("/ai/chat", params={"prompt": "hello"})
        assert response.status_code == 200
        assert response.json()["simulated"] is True
