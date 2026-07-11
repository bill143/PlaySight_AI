"""Feature-flagged module routers: 403 feature_disabled vs enabled 200/501."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from playsight.db.models import ClubModule
from tests.conftest import AuthContext

API = "/api/v1"


class TestFeatureFlagRouting:
    def test_disabled_module_returns_403_feature_disabled(
        self, client: TestClient, auth: AuthContext
    ) -> None:
        response = client.get(f"{API}/playbook/plays", headers=auth.headers)
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "feature_disabled"

    def test_club_override_enables_module(
        self, client: TestClient, auth: AuthContext, db: Session
    ) -> None:
        db.add(ClubModule(club_id=auth.club_id, module_key="playbook", enabled=True))
        db.commit()
        response = client.get(f"{API}/playbook/plays", headers=auth.headers)
        assert response.status_code in (200, 501)
        if response.status_code == 200:
            assert response.json() == []

    def test_override_is_per_club(self, client: TestClient, auth: AuthContext, db: Session) -> None:
        db.add(ClubModule(club_id=auth.club_id, module_key="playbook", enabled=True))
        db.commit()
        assert client.get(f"{API}/playbook/plays", headers=auth.headers).status_code in (200, 501)
        # Disabling again flips it back to 403 for the same club.
        override = (
            db.query(ClubModule)
            .filter(ClubModule.club_id == auth.club_id, ClubModule.module_key == "playbook")
            .one()
        )
        override.enabled = False
        db.commit()
        response = client.get(f"{API}/playbook/plays", headers=auth.headers)
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "feature_disabled"

    def test_globally_enabled_feature_passes_without_override(
        self, client: TestClient, auth: AuthContext
    ) -> None:
        # publishing_youtube defaults to true; a bad payload must reach the
        # router (422 validation), not be blocked by the feature gate (403).
        response = client.post(
            f"{API}/publish/youtube",
            json={"artifact_id": "missing", "title": "x", "confirm_rights": False},
            headers=auth.headers,
        )
        assert response.status_code == 422

    def test_all_phase2_module_routers_are_gated(
        self, client: TestClient, auth: AuthContext
    ) -> None:
        gated_paths = {
            "competition": "/competition/fixtures",
            "playbook": "/playbook/plays",
            "training": "/training/plans",
            "nutrition": "/nutrition/templates",
            "registration": "/registration/registrations",
        }
        for module_key, path in gated_paths.items():
            response = client.get(f"{API}{path}", headers=auth.headers)
            assert response.status_code == 403, f"{module_key}: {response.status_code}"
            assert response.json()["error"]["code"] == "feature_disabled", module_key
