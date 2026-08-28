from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

def test_full_trace_endpoint():
    response = client.get("/api/v1/trace_full")
    assert response.status_code == 200
    data = response.json()
    assert "timeseries" in data
    assert "reports" in data
