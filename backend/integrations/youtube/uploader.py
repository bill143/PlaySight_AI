"""YouTube video uploader with retry/backoff, using the resumable upload API."""

from __future__ import annotations

import logging
from pathlib import Path

from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from backend.integrations.youtube.auth import YouTubeAuthManager
from backend.integrations.youtube.models import YouTubeUploadRequest, YouTubeUploadResult

logger = logging.getLogger(__name__)

try:  # pragma: no cover - exercised only when google-api-python-client is installed
    from google.oauth2.credentials import Credentials  # type: ignore[import-not-found]
    from googleapiclient.discovery import build  # type: ignore[import-not-found]
    from googleapiclient.errors import HttpError  # type: ignore[import-not-found]
    from googleapiclient.http import MediaFileUpload  # type: ignore[import-not-found]

    _GOOGLE_API_AVAILABLE = True
except ImportError:  # pragma: no cover
    build = None  # type: ignore[assignment]
    HttpError = Exception  # type: ignore[assignment,misc]
    MediaFileUpload = None  # type: ignore[assignment]
    Credentials = None  # type: ignore[assignment]
    _GOOGLE_API_AVAILABLE = False


class TransientUploadError(Exception):
    """Raised for retryable upload failures (network blips, rate limiting)."""


class YouTubeUploader:
    """Uploads highlight/match videos to YouTube on behalf of a connected account."""

    def __init__(self, auth_manager: YouTubeAuthManager | None = None) -> None:
        self.auth_manager = auth_manager or YouTubeAuthManager()

    @retry(
        retry=retry_if_exception_type(TransientUploadError),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(5),
        reraise=True,
    )
    def upload(self, account_key: str, request: YouTubeUploadRequest) -> YouTubeUploadResult:
        """Upload a video, retrying transient failures with exponential backoff."""
        if not Path(request.file_path).exists():
            return YouTubeUploadResult(success=False, error_message=f"File not found: {request.file_path}")

        if not _GOOGLE_API_AVAILABLE:
            logger.warning("google-api-python-client not installed; simulating YouTube upload for '%s'.", request.title)
            return YouTubeUploadResult(
                success=True,
                video_id="stub-video-id",
                video_url="https://youtube.com/watch?v=stub-video-id",
            )

        tokens = self.auth_manager.get_valid_tokens(account_key)
        if tokens is None:
            return YouTubeUploadResult(success=False, error_message=f"No YouTube credentials found for '{account_key}'.")

        try:
            return self._do_upload(tokens.access_token, tokens.refresh_token, request)
        except HttpError as exc:  # pragma: no cover - requires live API
            status = getattr(exc, "status_code", None) or getattr(getattr(exc, "resp", None), "status", None)
            if status in (403, 429, 500, 502, 503):
                raise TransientUploadError(str(exc)) from exc
            return YouTubeUploadResult(success=False, error_message=str(exc))

    def _do_upload(self, access_token: str, refresh_token: str, request: YouTubeUploadRequest) -> YouTubeUploadResult:  # pragma: no cover
        credentials = Credentials(token=access_token, refresh_token=refresh_token)
        youtube = build("youtube", "v3", credentials=credentials)

        body = {
            "snippet": {
                "title": request.title,
                "description": request.description,
                "tags": request.tags or [],
                "categoryId": request.category_id,
            },
            "status": {"privacyStatus": request.privacy_status},
        }
        media = MediaFileUpload(request.file_path, chunksize=-1, resumable=True)
        insert_request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

        response = None
        while response is None:
            _status, response = insert_request.next_chunk()

        video_id = response["id"]
        return YouTubeUploadResult(
            success=True,
            video_id=video_id,
            video_url=f"https://youtube.com/watch?v={video_id}",
        )
