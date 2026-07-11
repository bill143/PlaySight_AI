"""YouTube OAuth2 upload integration (CONTRACTS.md section 13)."""

from playsight.integrations.youtube.client import (
    UploadResult,
    YouTubeClient,
    YouTubeUploadError,
    error_entry,
)
from playsight.integrations.youtube.service import publish_artifact, write_upload_status_artifact

__all__ = [
    "UploadResult",
    "YouTubeClient",
    "YouTubeUploadError",
    "error_entry",
    "publish_artifact",
    "write_upload_status_artifact",
]
