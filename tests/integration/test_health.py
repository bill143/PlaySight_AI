"""Health endpoints (no auth) — CONTRACTS.md section 12."""

from __future__ import annotations

from fastapi.testclient import TestClient

API = "/api/v1"


class TestHealth:
    def test_live(self, client: TestClient) -> None:
        response = client.get(f"{API}/health/live")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_ready_reports_database(self, client: TestClient) -> None:
        response = client.get(f"{API}/health/ready")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["checks"]["database"] == "ok"
        # redis_url is empty in the test environment, so no redis check runs.
        assert "redis" not in body["checks"]

    def test_health_requires_no_auth(self, client: TestClient) -> None:
        assert client.get(f"{API}/health/live").status_code == 200

    def test_protected_endpoint_requires_auth(self, client: TestClient) -> None:
        response = client.get(f"{API}/matches")
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "auth_error"
