"""Data models for the YouTube integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

PrivacyStatus = Literal["private", "unlisted", "public"]


@dataclass
class YouTubeUploadRequest:
    """Describes a request to upload a video to YouTube."""

    file_path: str
    title: str
    description: str = ""
    tags: list[str] | None = None
    privacy_status: PrivacyStatus = "private"
    category_id: str = "17"  # "Sports"


@dataclass
class YouTubeUploadResult:
    """Result of a (successful or failed) YouTube upload attempt."""

    success: bool
    video_id: str | None = None
    video_url: str | None = None
    error_message: str | None = None


@dataclass
class OAuthTokens:
    """OAuth2 token pair persisted for a connected YouTube account."""

    access_token: str
    refresh_token: str
    expires_at: float
    scope: str = "https://www.googleapis.com/auth/youtube.upload"
