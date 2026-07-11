"""Publishing endpoints: initiate uploads to external platforms (e.g. YouTube)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select

from backend.api.deps import DbSession, require_permission
from backend.core.exceptions import FeatureDisabledError, NotFoundError
from backend.core.feature_flags import feature_flags
from backend.core.rbac import Permission
from backend.models.artifact import Artifact
from backend.models.publishing import PublishRecord
from backend.models.user import User
from backend.workers.tasks.publish_tasks import publish_to_youtube_task

router = APIRouter(prefix="/publish", tags=["publishing"])


class YouTubePublishRequest(BaseModel):
    match_id: uuid.UUID
    artifact_id: uuid.UUID
    title: str
    description: str = ""
    privacy: str = "private"
    account_key: str = "default"


class PublishRecordRead(BaseModel):
    id: uuid.UUID
    match_id: uuid.UUID
    platform: str
    status: str
    external_url: str | None = None


@router.post("/youtube", response_model=PublishRecordRead, status_code=202)
async def publish_youtube(
    payload: YouTubePublishRequest,
    db: DbSession,
    _user: User = Depends(require_permission(Permission.PUBLISH_YOUTUBE)),
) -> PublishRecord:
    """Initiate an async upload of an artifact video to YouTube."""
    if not feature_flags.is_enabled("ENABLE_YOUTUBE_UPLOAD"):
        raise FeatureDisabledError("YouTube publishing is currently disabled (ENABLE_YOUTUBE_UPLOAD=false).")

    artifact_result = await db.execute(select(Artifact).where(Artifact.id == payload.artifact_id))
    artifact = artifact_result.scalar_one_or_none()
    if artifact is None:
        raise NotFoundError(f"Artifact {payload.artifact_id} not found")

    record = PublishRecord(
        match_id=payload.match_id,
        artifact_id=artifact.id,
        platform="youtube",
        status="pending",
        privacy=payload.privacy,
    )
    db.add(record)
    await db.flush()
    await db.commit()

    publish_to_youtube_task.delay(
        str(record.id),
        str(artifact.id),
        payload.account_key,
        payload.title,
        payload.description,
        payload.privacy,
    )

    return record
