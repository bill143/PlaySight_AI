"""Full API flow (CONTRACTS.md section 16).

register-club -> login -> create team + match -> upload tiny synthetic video ->
process (eager job, stub engines) -> poll job -> summary/events/stats ->
artifacts exist and download the exact bytes -> publish to a mocked YouTube ->
idempotent re-publish with the same Idempotency-Key.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import tests._env as _env
from playsight.integrations.youtube import UploadResult
from tests.conftest import AuthContext

API = "/api/v1"


class _FakeYouTubeClient:
    """Replaces YouTubeClient inside the publish service (no network)."""

    calls: list[dict] = []

    def __init__(self, settings=None) -> None:
        self._settings = settings

    def upload_video(self, file_path, **kwargs):
        _FakeYouTubeClient.calls.append({"file_path": str(file_path), **kwargs})
        if (progress_cb := kwargs.get("progress_cb")) is not None:
            progress_cb(1.0)
        return UploadResult(video_id="it-video-1", url="https://www.youtube.com/watch?v=it-video-1")


@pytest.fixture()
def mock_youtube(monkeypatch: pytest.MonkeyPatch) -> type[_FakeYouTubeClient]:
    _FakeYouTubeClient.calls = []
    monkeypatch.setattr("playsight.integrations.youtube.service.YouTubeClient", _FakeYouTubeClient)
    return _FakeYouTubeClient


def _create_team_and_match(client: TestClient, auth: AuthContext) -> str:
    team = client.post(
        f"{API}/teams",
        json={"name": "First XI", "sport": "soccer"},
        headers=auth.headers,
    )
    assert team.status_code == 201, team.text
    match = client.post(
        f"{API}/matches",
        json={"team_id": team.json()["id"], "opponent": "Rivals FC", "sport": "soccer"},
        headers=auth.headers,
    )
    assert match.status_code == 201, match.text
    return match.json()["id"]


def _upload_video(client: TestClient, auth: AuthContext, match_id: str, video: Path) -> dict:
    with video.open("rb") as fh:
        response = client.post(
            f"{API}/matches/{match_id}/videos",
            files={"file": (video.name, fh, "video/mp4")},
            headers=auth.headers,
        )
    assert response.status_code == 201, response.text
    return response.json()


def _process_match(client: TestClient, auth: AuthContext, match_id: str) -> dict:
    response = client.post(f"{API}/matches/{match_id}/process", headers=auth.headers)
    assert response.status_code == 202, response.text
    job_id = response.json()["job_id"]
    job = client.get(f"{API}/jobs/{job_id}", headers=auth.headers)
    assert job.status_code == 200, job.text
    body = job.json()
    assert body["status"] == "succeeded", f"analysis job failed: {body.get('error')}"
    return body


class TestFullMatchFlow:
    def test_end_to_end_process_and_publish(
        self,
        client: TestClient,
        auth: AuthContext,
        synthetic_video: Path,
        mock_youtube: type[_FakeYouTubeClient],
    ) -> None:
        match_id = _create_team_and_match(client, auth)

        # -- video upload (multipart) ------------------------------------------------
        asset = _upload_video(client, auth, match_id, synthetic_video)
        assert asset["status"] == "ready"
        assert asset["width"] == 64
        assert asset["height"] == 64
        assert asset["duration_s"] > 0

        # -- eager analysis job -------------------------------------------------------
        job = _process_match(client, auth, match_id)
        assert job["progress"] == 1.0
        assert job["kind"] == "analyze"
        result = job["result"]
        assert result["counts"]["tracks"] >= 1
        assert "match_summary" in result["artifact_paths"]

        match = client.get(f"{API}/matches/{match_id}", headers=auth.headers)
        assert match.json()["status"] == "processed"

        # -- summary / events / stats -------------------------------------------------
        summary = client.get(f"{API}/matches/{match_id}/summary", headers=auth.headers)
        assert summary.status_code == 200, summary.text
        payload = summary.json()
        assert payload["match_id"] == match_id
        assert payload["engine"]["detector"] == "stub"  # honest about stub engines
        assert payload["counts"]["tracks"] >= 1

        events = client.get(f"{API}/matches/{match_id}/events", headers=auth.headers)
        assert events.status_code == 200
        assert isinstance(events.json(), list)

        stats = client.get(f"{API}/matches/{match_id}/stats", headers=auth.headers)
        assert stats.status_code == 200, stats.text
        stats_rows = stats.json()
        assert len(stats_rows) >= 1
        for row in stats_rows:
            assert len(row["heatmap"]) == 8
            assert all(len(grid_row) == 12 for grid_row in row["heatmap"])

        # -- artifacts exist and stream the exact stored bytes -------------------------
        artifacts = client.get(
            f"{API}/artifacts", params={"match_id": match_id}, headers=auth.headers
        )
        assert artifacts.status_code == 200
        by_kind: dict[str, dict] = {}
        for artifact in artifacts.json():
            by_kind.setdefault(artifact["kind"], artifact)
        for kind in ("player_tracks", "player_identities", "player_stats", "match_summary"):
            assert kind in by_kind, f"missing artifact kind {kind}: {sorted(by_kind)}"

        summary_artifact = by_kind["match_summary"]
        download = client.get(
            f"{API}/artifacts/{summary_artifact['id']}/download", headers=auth.headers
        )
        assert download.status_code == 200
        assert download.headers["content-type"].startswith("application/json")
        assert summary_artifact["filename"] in download.headers["content-disposition"]
        stored = (_env.STORAGE_ROOT / summary_artifact["storage_key"]).read_bytes()
        assert download.content == stored
        assert json.loads(download.content)["match_id"] == match_id

        if "player_report_pdf" in by_kind:
            pdf = client.get(
                f"{API}/artifacts/{by_kind['player_report_pdf']['id']}/download",
                headers=auth.headers,
            )
            assert pdf.status_code == 200
            assert pdf.content.startswith(b"%PDF")

        # -- publish to (mocked) YouTube ------------------------------------------------
        publish = client.post(
            f"{API}/publish/youtube",
            json={
                "artifact_id": summary_artifact["id"],
                "title": "Match summary artifact",
                "description": "Automated test publish",
                "tags": ["playsight", "test"],
                "privacy": "private",
                "confirm_rights": True,
            },
            headers={**auth.headers, "Idempotency-Key": "flow-key-1"},
        )
        assert publish.status_code == 201, publish.text
        upload_id = publish.json()["upload_id"]
        job_id = publish.json()["job_id"]
        assert job_id

        record = client.get(f"{API}/publish/{upload_id}", headers=auth.headers)
        assert record.status_code == 200, record.text
        record_body = record.json()
        assert record_body["status"] == "succeeded"
        assert record_body["platform_video_id"] == "it-video-1"
        assert record_body["url"] == "https://www.youtube.com/watch?v=it-video-1"
        assert record_body["idempotency_key"] == "flow-key-1"
        assert len(mock_youtube.calls) == 1
        assert mock_youtube.calls[0]["privacy"] == "private"

        publish_job = client.get(f"{API}/jobs/{job_id}", headers=auth.headers)
        assert publish_job.json()["status"] == "succeeded"

        # -- idempotent re-publish: same key, same record, no second upload ------------
        repeat = client.post(
            f"{API}/publish/youtube",
            json={
                "artifact_id": summary_artifact["id"],
                "title": "Match summary artifact",
                "confirm_rights": True,
            },
            headers={**auth.headers, "Idempotency-Key": "flow-key-1"},
        )
        assert repeat.status_code == 200, repeat.text
        assert repeat.json()["upload_id"] == upload_id
        assert len(mock_youtube.calls) == 1  # no re-upload happened

        # upload_status.json artifact was refreshed after the terminal state.
        status_artifacts = client.get(
            f"{API}/artifacts",
            params={"match_id": match_id, "kind": "upload_status"},
            headers=auth.headers,
        )
        assert len(status_artifacts.json()) == 1

    def test_publish_requires_rights_confirmation(
        self,
        client: TestClient,
        auth: AuthContext,
        synthetic_video: Path,
        mock_youtube: type[_FakeYouTubeClient],
    ) -> None:
        match_id = _create_team_and_match(client, auth)
        _upload_video(client, auth, match_id, synthetic_video)
        _process_match(client, auth, match_id)
        artifacts = client.get(
            f"{API}/artifacts",
            params={"match_id": match_id, "kind": "match_summary"},
            headers=auth.headers,
        )
        artifact_id = artifacts.json()[0]["id"]

        response = client.post(
            f"{API}/publish/youtube",
            json={"artifact_id": artifact_id, "title": "No rights", "confirm_rights": False},
            headers=auth.headers,
        )
        assert response.status_code == 422
        assert "rights" in response.json()["error"]["message"].lower()
        assert mock_youtube.calls == []

    def test_process_without_video_fails_validation(
        self, client: TestClient, auth: AuthContext
    ) -> None:
        match_id = _create_team_and_match(client, auth)
        response = client.post(f"{API}/matches/{match_id}/process", headers=auth.headers)
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "validation_failed"

    def test_refresh_token_rejected_as_access_token(
        self, client: TestClient, auth: AuthContext
    ) -> None:
        login = client.post(
            f"{API}/auth/login", json={"email": auth.email, "password": auth.password}
        )
        refresh_token = login.json()["refresh_token"]
        response = client.get(
            f"{API}/auth/me", headers={"Authorization": f"Bearer {refresh_token}"}
        )
        assert response.status_code == 401
