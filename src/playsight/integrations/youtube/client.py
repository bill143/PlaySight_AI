"""YouTube Data API v3 client: OAuth2 installed-app flow + resumable uploads.

Implements CONTRACTS.md section 13. Google client libraries are imported
lazily inside methods so importing this module stays cheap and side-effect
free. The googleapiclient service object is created in a single small seam,
:meth:`YouTubeClient._build_service`, which tests patch with a mock.

Safety invariant (CONTRACTS.md section 18): uploads default to ``private``
privacy and this client never auto-publishes; callers must opt in explicitly.
"""

from __future__ import annotations

import http.client
import mimetypes
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tenacity import Retrying, retry_if_exception, stop_after_attempt, wait_exponential

from playsight.config.settings import Settings, get_settings
from playsight.core.errors import AuthError, ExternalServiceError, ValidationFailed
from playsight.core.logging import get_logger

log = get_logger(__name__)

YOUTUBE_UPLOAD_SCOPE = "https://www.googleapis.com/auth/youtube.upload"
SCOPES = [YOUTUBE_UPLOAD_SCOPE]
WATCH_URL_TEMPLATE = "https://www.youtube.com/watch?v={video_id}"
DEFAULT_CHUNK_SIZE = 8 * 1024 * 1024
MAX_UPLOAD_ATTEMPTS = 5
VALID_PRIVACY_STATUSES = ("private", "unlisted", "public")

#: Google API error ``reason`` values that indicate transient quota/backend
#: pressure worth retrying (only relevant for HTTP 403 responses).
_RETRYABLE_REASONS = frozenset(
    {
        "quotaExceeded",
        "userRateLimitExceeded",
        "rateLimitExceeded",
        "backendError",
        "internalError",
    }
)


@dataclass(frozen=True)
class UploadResult:
    """Outcome of a successful YouTube upload."""

    video_id: str
    url: str


def error_entry(stage: str, error: str, retryable: bool) -> dict[str, Any]:
    """Build a structured error-log entry for ``upload_records.error_log_json``.

    Args:
        stage: Pipeline stage where the failure happened (e.g. ``"download"``,
            ``"upload"``, ``"finalize"``).
        error: Human-readable error description.
        retryable: Whether the failure was classified as transient.

    Returns:
        ``{"at": iso_ts, "stage": str, "error": str, "retryable": bool}``.
    """
    return {
        "at": datetime.now(UTC).isoformat(),
        "stage": stage,
        "error": error,
        "retryable": retryable,
    }


class YouTubeUploadError(ExternalServiceError):
    """Terminal upload failure carrying structured error-log entries.

    ``error_log`` is a list of :func:`error_entry` dicts that the publish
    service appends to ``upload_records.error_log_json``.
    """

    default_code = "youtube_upload_failed"

    def __init__(self, message: str, error_log: list[dict[str, Any]] | None = None) -> None:
        """Create the error with an optional list of structured log entries."""
        super().__init__(message)
        self.error_log: list[dict[str, Any]] = list(error_log or [])


def _http_status_of(exc: BaseException) -> int | None:
    """Return the HTTP status of a googleapiclient ``HttpError``-like exception.

    Duck-typed via ``exc.resp.status`` so tests can raise plain fakes and the
    check never needs to import googleapiclient.
    """
    resp = getattr(exc, "resp", None)
    status = getattr(resp, "status", None)
    if status is None:
        return None
    try:
        return int(status)
    except (TypeError, ValueError):
        return None


def _has_quota_reason(exc: BaseException) -> bool:
    """Return whether an HTTP 403 error carries a quota/rate-limit reason."""
    details = getattr(exc, "error_details", None) or []
    for detail in details:
        if isinstance(detail, dict) and detail.get("reason") in _RETRYABLE_REASONS:
            return True
    content = getattr(exc, "content", b"") or b""
    text = str(content)
    if isinstance(content, bytes | bytearray):
        text = content.decode("utf-8", "replace")
    return any(reason in text for reason in _RETRYABLE_REASONS)


def _is_transient_error(exc: BaseException) -> bool:
    """Classify an upload exception as transient (retryable) or permanent.

    Retryable: HTTP 5xx, HTTP 429, quota/rate-limit 403s, and socket-level
    errors. Everything else (bad request, invalid auth, bad metadata) is
    permanent and fails fast without retries.
    """
    status = _http_status_of(exc)
    if status is not None:
        if status >= 500 or status == 429:
            return True
        return status == 403 and _has_quota_reason(exc)
    return isinstance(exc, OSError | http.client.HTTPException)


class YouTubeClient:
    """Uploads videos to YouTube via the OAuth2 installed-app flow.

    Token json is persisted to ``settings.youtube.token_file`` and refreshed
    automatically when expired. Construction is side-effect free: no Google
    library is imported and no network call happens until a method needs it.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        """Store settings; defer all client construction to first use.

        Args:
            settings: Application settings; defaults to the process-wide
                cached settings.
        """
        self._settings = settings or get_settings()

    # -- OAuth2 -----------------------------------------------------------------

    def get_authorize_url(self) -> str:
        """Return the Google OAuth2 consent URL for the installed-app flow."""
        flow = self._create_flow()
        flow.redirect_uri = "http://localhost"
        url, _state = flow.authorization_url(
            access_type="offline", include_granted_scopes="true", prompt="consent"
        )
        return str(url)

    def run_local_auth(self) -> Path:
        """Run the local-server OAuth2 consent flow and persist the token json.

        Opens the system browser and listens on an ephemeral localhost port
        for the redirect. Used by ``playsight youtube auth``.

        Returns:
            Path of the persisted token file.

        Raises:
            ValidationFailed: The client secrets file is missing.
        """
        flow = self._create_flow()
        credentials = flow.run_local_server(port=0, open_browser=True)
        token_path = self._save_credentials(credentials)
        log.info("youtube_auth_completed", token_file=str(token_path))
        return token_path

    def _create_flow(self) -> Any:
        """Build the google-auth-oauthlib installed-app flow (lazy import)."""
        from google_auth_oauthlib.flow import InstalledAppFlow

        secrets_path = Path(self._settings.youtube.client_secrets_file)
        if not secrets_path.is_file():
            raise ValidationFailed(
                f"Google client secrets file not found: {secrets_path}. Download an OAuth "
                "client (Desktop app) json from the Google Cloud Console and place it there."
            )
        return InstalledAppFlow.from_client_secrets_file(str(secrets_path), scopes=SCOPES)

    def _load_credentials(self) -> Any:
        """Load persisted credentials, refreshing (and re-persisting) if expired.

        Raises:
            AuthError: No token file, or the token is unusable and cannot be
                refreshed (``playsight youtube auth`` must be re-run).
            ExternalServiceError: The refresh round-trip to Google failed.
        """
        from google.oauth2.credentials import Credentials

        token_path = Path(self._settings.youtube.token_file)
        if not token_path.is_file():
            raise AuthError(
                f"YouTube token file not found: {token_path}. Run `playsight youtube auth`."
            )
        credentials = Credentials.from_authorized_user_file(str(token_path), scopes=SCOPES)
        if credentials.valid:
            return credentials
        if credentials.expired and credentials.refresh_token:
            from google.auth.transport.requests import Request

            try:
                credentials.refresh(Request())
            except Exception as exc:
                raise ExternalServiceError(
                    f"Failed to refresh YouTube OAuth token: {exc}",
                ) from exc
            self._save_credentials(credentials)
            log.info("youtube_token_refreshed", token_file=str(token_path))
            return credentials
        raise AuthError(
            "YouTube credentials are invalid and cannot be refreshed; "
            "re-run `playsight youtube auth`."
        )

    def _save_credentials(self, credentials: Any) -> Path:
        """Persist credentials json to ``settings.youtube.token_file``."""
        token_path = Path(self._settings.youtube.token_file)
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(credentials.to_json(), encoding="utf-8")
        return token_path

    # -- Service construction (single seam for tests) ---------------------------

    def _build_service(self) -> Any:
        """Build the googleapiclient YouTube service object.

        Kept as one small method so tests can patch it with a mock instead of
        exercising googleapiclient discovery.
        """
        from googleapiclient.discovery import build

        credentials = self._load_credentials()
        return build("youtube", "v3", credentials=credentials, cache_discovery=False)

    # -- Upload ------------------------------------------------------------------

    def upload_video(
        self,
        file_path: str | Path,
        *,
        title: str,
        description: str = "",
        tags: Sequence[str] | None = None,
        category_id: str = "17",
        privacy: str = "private",
        progress_cb: Callable[[float], None] | None = None,
    ) -> UploadResult:
        """Upload a local video file with resumable chunks and bounded retries.

        Retries (tenacity, exponential backoff, max 5 attempts) apply only to
        transient failures: HTTP 5xx, 429, quota-flavored 403s, and socket
        errors. Permanent failures raise immediately.

        Args:
            file_path: Path to the local video file.
            title: Video title.
            description: Video description.
            tags: Optional tag list.
            category_id: YouTube category id; default ``"17"`` (Sports).
            privacy: ``private`` (default) | ``unlisted`` | ``public``. Never
                auto-publishes; anything beyond private is an explicit opt-in.
            progress_cb: Optional callback receiving progress in ``[0, 1]``.

        Returns:
            UploadResult with the video id and its watch URL.

        Raises:
            ValidationFailed: Missing file or invalid ``privacy`` value.
            AuthError: No usable OAuth token (run ``playsight youtube auth``).
            ExternalServiceError: Terminal upload failure; the raised
                :class:`YouTubeUploadError` carries structured ``error_log``
                entries for ``upload_records.error_log_json``.
        """
        path = Path(file_path)
        if not path.is_file():
            raise ValidationFailed(f"Video file not found: {path}")
        if privacy not in VALID_PRIVACY_STATUSES:
            raise ValidationFailed(
                f"Invalid privacy {privacy!r}; expected one of {VALID_PRIVACY_STATUSES}"
            )

        service = self._build_service()
        from googleapiclient.http import MediaFileUpload

        body = {
            "snippet": {
                "title": title,
                "description": description,
                "tags": list(tags or []),
                "categoryId": category_id,
            },
            "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False},
        }
        media = MediaFileUpload(
            str(path),
            mimetype=mimetypes.guess_type(path.name)[0] or "video/mp4",
            chunksize=DEFAULT_CHUNK_SIZE,
            resumable=True,
        )
        request = service.videos().insert(part="snippet,status", body=body, media_body=media)

        log.info(
            "youtube_upload_started",
            file=str(path),
            size_bytes=path.stat().st_size,
            title=title,
            privacy=privacy,
        )
        error_log: list[dict[str, Any]] = []
        retryer = Retrying(
            stop=stop_after_attempt(MAX_UPLOAD_ATTEMPTS),
            wait=wait_exponential(multiplier=1.0, min=1.0, max=60.0),
            retry=retry_if_exception(_is_transient_error),
            reraise=True,
        )
        try:
            response = retryer(self._attempt_upload, request, progress_cb, error_log)
        except Exception as exc:
            raise YouTubeUploadError(
                f"YouTube upload failed: {exc}",
                error_log=error_log,
            ) from exc

        video_id = str(response.get("id") or "")
        if not video_id:
            error_log.append(error_entry("finalize", "YouTube response missing video id", False))
            raise YouTubeUploadError("YouTube upload returned no video id", error_log=error_log)
        if progress_cb is not None:
            progress_cb(1.0)
        url = WATCH_URL_TEMPLATE.format(video_id=video_id)
        log.info("youtube_upload_succeeded", video_id=video_id, url=url)
        return UploadResult(video_id=video_id, url=url)

    def _attempt_upload(
        self,
        request: Any,
        progress_cb: Callable[[float], None] | None,
        error_log: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Run one upload attempt, recording a structured entry on failure."""
        try:
            return self._drive_resumable_upload(request, progress_cb)
        except Exception as exc:
            retryable = _is_transient_error(exc)
            error_log.append(error_entry("upload", f"{type(exc).__name__}: {exc}", retryable))
            log.warning("youtube_upload_attempt_failed", error=str(exc), retryable=retryable)
            raise

    @staticmethod
    def _drive_resumable_upload(
        request: Any, progress_cb: Callable[[float], None] | None
    ) -> dict[str, Any]:
        """Drive the resumable upload chunk loop until the API returns a body."""
        response: dict[str, Any] | None = None
        while response is None:
            status, response = request.next_chunk()
            if status is not None and progress_cb is not None:
                progress_cb(min(float(status.progress()), 0.99))
        return response
