from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)

def test_watch_endpoint():
    response = client.post("/api/watch", json={"path": "/mock/path"})
    assert response.status_code == 200
    assert response.json()["status"] == "watching"
