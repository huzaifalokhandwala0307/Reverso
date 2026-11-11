from __future__ import annotations

from unittest.mock import MagicMock

from backend.app.database import get_db
from backend.app.main import app
from fastapi.testclient import TestClient


def test_health_liveness(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_readiness_healthy(client: TestClient):
    response = client.get("/health/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["database"] == "connected"


def test_health_readiness_db_down(client: TestClient):
    def failing_db():
        mock = MagicMock()
        mock.execute.side_effect = Exception("Connection refused to database")
        yield mock

    app.dependency_overrides[get_db] = failing_db
    try:
        response = client.get("/health/ready")
        assert response.status_code == 503
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "database_unavailable"
        assert "Connection refused" in data["error"]["details"]
    finally:
        app.dependency_overrides.pop(get_db, None)
