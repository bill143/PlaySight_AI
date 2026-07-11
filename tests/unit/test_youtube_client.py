"""YouTube client: transient retry, quota failure with structured error log.

The googleapiclient service object is replaced through the single
``YouTubeClient._build_service`` seam; no network traffic happens.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import pytest

from playsight.config.settings import Settings
from playsight.core.errors import ValidationFailed
from playsight.integrations.youtube.client import (
    MAX_UPLOAD_ATTEMPTS,
    UploadResult,
    YouTubeClient,
    YouTubeUploadError,
    _is_transient_error,
    error_entry,
)


class _FakeResp:
    def __init__(self, status: int) -> None:
        self.status = status


class _FakeHttpError(Exception):
    """Duck-typed googleapiclient HttpError (resp.status + content)."""

    def __init__(self, status: int, content: bytes = b"") -> None:
        super().__init__(f"HTTP {status}")
        self.resp = _FakeResp(status)
        self.content = content


class _FakeRequest:
    """Resumable-upload request raising scripted errors before succeeding."""

    def __init__(self, failures: list[Exception], video_id: str = "vid123") -> None:
        self._failures = list(failures)
        self._video_id = video_id
        self.calls = 0

    def next_chunk(self) -> tuple[None, dict[str, Any]]:
        self.calls += 1
        if self._failures:
            raise self._failures.pop(0)
        return None, {"id": self._video_id}


class _AlwaysFailRequest:
    def __init__(self, error_factory) -> None:
        self._error_factory = error_factory
        self.calls = 0

    def next_chunk(self) -> tuple[None, dict[str, Any]]:
        self.calls += 1
        raise self._error_factory()


class _FakeVideos:
    def __init__(self, request: Any) -> None:
        self._request = request
        self.insert_kwargs: dict[str, Any] | None = None

    def insert(self, **kwargs: Any) -> Any:
        self.insert_kwargs = kwargs
        return self._request


class _FakeService:
    def __init__(self, request: Any) -> None:
        self.videos_api = _FakeVideos(request)

    def videos(self) -> _FakeVideos:
        return self.videos_api


@pytest.fixture()
def video_file(tmp_path: Path) -> Path:
    path = tmp_path / "clip.mp4"
    path.write_bytes(b"\x00" * 1024)
    return path


@pytest.fixture()
def _no_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    """Neutralize tenacity's exponential backoff sleeps."""
    monkeypatch.setattr(time, "sleep", lambda seconds: None)


def _client_with(monkeypatch: pytest.MonkeyPatch, request: Any) -> YouTubeClient:
    client = YouTubeClient(Settings(_env_file=None))
    monkeypatch.setattr(client, "_build_service", lambda: _FakeService(request))
    return client


@pytest.mark.usefixtures("_no_sleep")
class TestUploadRetries:
    def test_transient_503_then_success_retries(
        self, monkeypatch: pytest.MonkeyPatch, video_file: Path
    ) -> None:
        request = _FakeRequest([_FakeHttpError(503)])
        client = _client_with(monkeypatch, request)
        progress: list[float] = []

        result = client.upload_video(
            video_file, title="Match highlights", progress_cb=progress.append
        )

        assert request.calls == 2  # first attempt failed, retry succeeded
        assert isinstance(result, UploadResult)
        assert result.video_id == "vid123"
        assert result.url == "https://www.youtube.com/watch?v=vid123"
        assert progress[-1] == 1.0

    def test_persistent_quota_error_fails_with_structured_log(
        self, monkeypatch: pytest.MonkeyPatch, video_file: Path
    ) -> None:
        request = _AlwaysFailRequest(
            lambda: _FakeHttpError(403, content=b'{"reason": "quotaExceeded"}')
        )
        client = _client_with(monkeypatch, request)

        with pytest.raises(YouTubeUploadError) as excinfo:
            client.upload_video(video_file, title="Quota-bound upload")

        error = excinfo.value
        assert error.code == "youtube_upload_failed"
        assert request.calls == MAX_UPLOAD_ATTEMPTS
        assert len(error.error_log) == MAX_UPLOAD_ATTEMPTS
        for entry in error.error_log:
            assert set(entry) == {"at", "stage", "error", "retryable"}
            assert entry["stage"] == "upload"
            assert entry["retryable"] is True

    def test_permanent_error_fails_fast(
        self, monkeypatch: pytest.MonkeyPatch, video_file: Path
    ) -> None:
        request = _AlwaysFailRequest(lambda: _FakeHttpError(400))
        client = _client_with(monkeypatch, request)

        with pytest.raises(YouTubeUploadError) as excinfo:
            client.upload_video(video_file, title="Bad request")

        assert request.calls == 1  # no retries on permanent failures
        assert len(excinfo.value.error_log) == 1
        assert excinfo.value.error_log[0]["retryable"] is False

    def test_metadata_and_privacy_forwarded(
        self, monkeypatch: pytest.MonkeyPatch, video_file: Path
    ) -> None:
        request = _FakeRequest([])
        client = YouTubeClient(Settings(_env_file=None))
        service = _FakeService(request)
        monkeypatch.setattr(client, "_build_service", lambda: service)

        client.upload_video(
            video_file,
            title="Title",
            description="Desc",
            tags=["a", "b"],
            category_id="17",
            privacy="private",
        )

        kwargs = service.videos_api.insert_kwargs
        assert kwargs is not None
        body = kwargs["body"]
        assert body["snippet"] == {
            "title": "Title",
            "description": "Desc",
            "tags": ["a", "b"],
            "categoryId": "17",
        }
        assert body["status"]["privacyStatus"] == "private"
        assert kwargs["part"] == "snippet,status"


class TestUploadValidation:
    def test_missing_file_rejected(self, tmp_path: Path) -> None:
        client = YouTubeClient(Settings(_env_file=None))
        with pytest.raises(ValidationFailed):
            client.upload_video(tmp_path / "nope.mp4", title="x")

    def test_invalid_privacy_rejected(self, video_file: Path) -> None:
        client = YouTubeClient(Settings(_env_file=None))
        with pytest.raises(ValidationFailed):
            client.upload_video(video_file, title="x", privacy="everyone")


class TestTransientClassification:
    def test_5xx_and_429_are_transient(self) -> None:
        assert _is_transient_error(_FakeHttpError(500)) is True
        assert _is_transient_error(_FakeHttpError(503)) is True
        assert _is_transient_error(_FakeHttpError(429)) is True

    def test_plain_403_is_permanent_but_quota_403_is_transient(self) -> None:
        assert _is_transient_error(_FakeHttpError(403)) is False
        quota = _FakeHttpError(403, content=b"userRateLimitExceeded")
        assert _is_transient_error(quota) is True

    def test_socket_errors_are_transient(self) -> None:
        assert _is_transient_error(ConnectionResetError("reset")) is True

    def test_value_error_is_permanent(self) -> None:
        assert _is_transient_error(ValueError("boom")) is False

    def test_error_entry_shape(self) -> None:
        entry = error_entry("upload", "boom", True)
        assert set(entry) == {"at", "stage", "error", "retryable"}
        assert entry["retryable"] is True
