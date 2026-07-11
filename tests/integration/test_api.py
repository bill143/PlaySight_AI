"""Integration tests exercising the FastAPI app via HTTP (httpx AsyncClient)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


class TestHealthEndpoints:
    async def test_health_check(self, client: AsyncClient) -> None:
        response = await client.get("/api/v1/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    async def test_readiness_check(self, client: AsyncClient) -> None:
        response = await client.get("/api/v1/health/ready")
        assert response.status_code == 200
        assert response.json()["status"] == "ready"


class TestAuthEndpoints:
    async def test_login_succeeds_with_valid_credentials(self, client: AsyncClient, test_user) -> None:
        response = await client.post(
            "/api/v1/auth/login", json={"email": test_user.email, "password": "password123"}
        )
        assert response.status_code == 200
        body = response.json()
        assert "access_token" in body
        assert "refresh_token" in body

    async def test_login_fails_with_invalid_password(self, client: AsyncClient, test_user) -> None:
        response = await client.post(
            "/api/v1/auth/login", json={"email": test_user.email, "password": "wrong-password"}
        )
        assert response.status_code == 401

    async def test_refresh_returns_new_token_pair(self, client: AsyncClient, test_user) -> None:
        login_response = await client.post(
            "/api/v1/auth/login", json={"email": test_user.email, "password": "password123"}
        )
        refresh_token = login_response.json()["refresh_token"]

        response = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
        assert response.status_code == 200
        assert "access_token" in response.json()


class TestMatchesEndpoints:
    async def test_list_matches_requires_authentication(self, client: AsyncClient) -> None:
        response = await client.get("/api/v1/matches")
        assert response.status_code in (401, 403)

    async def test_list_matches_returns_empty_list(self, client: AsyncClient, auth_headers: dict[str, str]) -> None:
        response = await client.get("/api/v1/matches", headers=auth_headers)
        assert response.status_code == 200
        assert response.json() == []

    async def test_get_nonexistent_match_returns_404(self, client: AsyncClient, auth_headers: dict[str, str]) -> None:
        response = await client.get(
            "/api/v1/matches/00000000-0000-0000-0000-000000000000", headers=auth_headers
        )
        assert response.status_code == 404
