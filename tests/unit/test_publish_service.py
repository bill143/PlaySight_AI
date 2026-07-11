"""Publish service: upload-record lifecycle, idempotency, structured errors."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from playsight.core.errors import NotFoundError
from playsight.db.models import Artifact, Club, UploadRecord
from playsight.integrations.youtube import (
    UploadResult,
    YouTubeUploadError,
    error_entry,
    publish_artifact,
)
from playsight.storage import LocalStorage


class _FakeYouTubeClient:
    """Stands in for YouTubeClient; counts uploads and can be scripted to fail."""

    def __init__(self, fail_with: Exception | None = None) -> None:
        self.fail_with = fail_with
        self.calls: list[dict] = []

    def upload_video(self, file_path, **kwargs):
        self.calls.append({"file_path": Path(file_path), **kwargs})
        if self.fail_with is not None:
            raise self.fail_with
        return UploadResult(
            video_id="fake-video-id", url="https://www.youtube.com/watch?v=fake-video-id"
        )


def _seed_record(db: Session, storage: LocalStorage, key: str = "artifacts/demo.mp4") -> str:
    """Create club + stored artifact + pending upload record; returns record id."""
    club = Club(name="Publish Club", slug=f"publish-club-{key.replace('/', '-')}")
    db.add(club)
    db.flush()
    storage.put_bytes(b"pretend-video-bytes", key)
    artifact = Artifact(
        club_id=club.id,
        match_id=None,
        kind="player_highlights",
        storage_key=key,
        filename=Path(key).name,
        content_type="video/mp4",
        size_bytes=19,
        meta_json={},
    )
    db.add(artifact)
    db.flush()
    record = UploadRecord(
        club_id=club.id,
        artifact_id=artifact.id,
        platform="youtube",
        idempotency_key=f"idem-{key}",
        status="pending",
        title="Test upload",
        description="",
        tags_json=[],
        category_id="17",
        privacy="private",
    )
    db.add(record)
    db.commit()
    return record.id


@pytest.fixture()
def storage(tmp_path: Path) -> LocalStorage:
    return LocalStorage(tmp_path / "publish-store")


class TestPublishArtifact:
    def test_success_updates_record(self, db: Session, storage: LocalStorage) -> None:
        record_id = _seed_record(db, storage)
        client = _FakeYouTubeClient()
        record = publish_artifact(db, storage, record_id, client=client)
        assert record.status == "succeeded"
        assert record.platform_video_id == "fake-video-id"
        assert record.url == "https://www.youtube.com/watch?v=fake-video-id"
        assert record.attempts == 1
        assert len(client.calls) == 1
        assert client.calls[0]["title"] == "Test upload"
        assert client.calls[0]["privacy"] == "private"

    def test_succeeded_record_is_idempotent(self, db: Session, storage: LocalStorage) -> None:
        record_id = _seed_record(db, storage)
        client = _FakeYouTubeClient()
        publish_artifact(db, storage, record_id, client=client)
        again = publish_artifact(db, storage, record_id, client=client)
        assert again.status == "succeeded"
        assert len(client.calls) == 1  # no second upload
        assert again.attempts == 1

    def test_failure_appends_structured_error_log(self, db: Session, storage: LocalStorage) -> None:
        record_id = _seed_record(db, storage)
        failure = YouTubeUploadError(
            "quota exhausted", error_log=[error_entry("upload", "quotaExceeded", True)]
        )
        client = _FakeYouTubeClient(fail_with=failure)
        with pytest.raises(YouTubeUploadError):
            publish_artifact(db, storage, record_id, client=client)
        db.expire_all()
        record = db.get(UploadRecord, record_id)
        assert record is not None
        assert record.status == "failed"
        assert record.attempts == 1
        assert len(record.error_log_json) == 1
        entry = record.error_log_json[0]
        assert set(entry) == {"at", "stage", "error", "retryable"}
        assert entry["error"] == "quotaExceeded"

    def test_unknown_record_raises_not_found(self, db: Session, storage: LocalStorage) -> None:
        with pytest.raises(NotFoundError):
            publish_artifact(db, storage, "does-not-exist", client=_FakeYouTubeClient())

    def test_missing_storage_object_marks_failed(self, db: Session, storage: LocalStorage) -> None:
        record_id = _seed_record(db, storage)
        storage.delete("artifacts/demo.mp4")
        client = _FakeYouTubeClient()
        with pytest.raises(YouTubeUploadError):
            publish_artifact(db, storage, record_id, client=client)
        db.expire_all()
        record = db.get(UploadRecord, record_id)
        assert record is not None
        assert record.status == "failed"
        assert record.error_log_json[0]["stage"] == "download"
        assert client.calls == []
