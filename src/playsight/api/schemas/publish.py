"""YouTube publishing models (CONTRACTS.md sections 12-13, 18)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class PublishRequest(BaseModel):
    """Request to publish an artifact to YouTube.

    ``confirm_rights`` must be explicitly true: the caller confirms they hold
    the rights to publish the footage (legal invariant, section 18). Privacy
    defaults to ``private``; the platform never auto-publishes.
    """

    artifact_id: str
    title: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=5000)
    tags: list[str] = Field(default_factory=list, max_length=50)
    category_id: str = "17"  # YouTube category: Sports
    privacy: Literal["private", "unlisted", "public"] = "private"
    confirm_rights: bool = False


class PublishAccepted(BaseModel):
    """Accepted publish request: the upload record and its processing job."""

    upload_id: str
    job_id: str | None = None
    status: str = "pending"


class UploadRecordRead(BaseModel):
    """Full upload record (idempotent per ``Idempotency-Key``)."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    club_id: str
    artifact_id: str
    platform: str
    idempotency_key: str
    status: str
    platform_video_id: str | None = None
    url: str | None = None
    title: str
    description: str
    tags: list[str] = Field(default_factory=list, validation_alias="tags_json")
    category_id: str
    privacy: str
    error_log: list[dict[str, Any]] = Field(default_factory=list, validation_alias="error_log_json")
    attempts: int
    created_at: datetime
    updated_at: datetime
