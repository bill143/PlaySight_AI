"""Tenancy isolation: cross-club access answers 404 (CONTRACTS.md section 6)."""

from __future__ import annotations

from collections.abc import Callable

from fastapi.testclient import TestClient

from tests.conftest import AuthContext

API = "/api/v1"


def _create_match(client: TestClient, auth: AuthContext) -> str:
    team = client.post(
        f"{API}/teams",
        json={"name": "Tenancy XI", "sport": "soccer"},
        headers=auth.headers,
    )
    assert team.status_code == 201, team.text
    match = client.post(
        f"{API}/matches",
        json={"team_id": team.json()["id"], "opponent": "Ghost FC", "sport": "soccer"},
        headers=auth.headers,
    )
    assert match.status_code == 201, match.text
    return match.json()["id"]


class TestTenancyIsolation:
    def test_club_b_gets_404_on_club_a_match(
        self,
        client: TestClient,
        auth: AuthContext,
        make_club: Callable[[str], AuthContext],
    ) -> None:
        match_id = _create_match(client, auth)
        club_b = make_club("b")

        own = client.get(f"{API}/matches/{match_id}", headers=auth.headers)
        assert own.status_code == 200

        foreign = client.get(f"{API}/matches/{match_id}", headers=club_b.headers)
        assert foreign.status_code == 404  # 404, not 403: never leak existence
        assert foreign.json()["error"]["code"] == "not_found"

    def test_club_b_cannot_see_club_a_lists(
        self,
        client: TestClient,
        auth: AuthContext,
        make_club: Callable[[str], AuthContext],
    ) -> None:
        _create_match(client, auth)
        club_b = make_club("b")

        matches_b = client.get(f"{API}/matches", headers=club_b.headers)
        assert matches_b.status_code == 200
        assert matches_b.json() == []

        teams_b = client.get(f"{API}/teams", headers=club_b.headers)
        assert teams_b.json() == []

        jobs_b = client.get(f"{API}/jobs", headers=club_b.headers)
        assert jobs_b.json() == []

        artifacts_b = client.get(f"{API}/artifacts", headers=club_b.headers)
        assert artifacts_b.json() == []

    def test_club_b_cannot_process_club_a_match(
        self,
        client: TestClient,
        auth: AuthContext,
        make_club: Callable[[str], AuthContext],
    ) -> None:
        match_id = _create_match(client, auth)
        club_b = make_club("b")
        response = client.post(f"{API}/matches/{match_id}/process", headers=club_b.headers)
        assert response.status_code == 404

    def test_bootstrap_closed_once_a_club_exists(
        self, client: TestClient, auth: AuthContext
    ) -> None:
        # env=test: register-club is open only while no clubs exist.
        response = client.post(
            f"{API}/auth/register-club",
            json={
                "club_name": "Second Club",
                "slug": "second-club",
                "email": "second@example.com",
                "password": "AnotherPass123",
                "full_name": "Second Admin",
            },
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "permission_denied"
