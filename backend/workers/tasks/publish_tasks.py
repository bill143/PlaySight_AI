"""Celery tasks for publishing artifacts to external platforms (e.g. YouTube)."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

from sqlalchemy import select

from backend.core.database import AsyncSessionLocal
from backend.core.storage import get_storage_client
from backend.integrations.youtube.models import YouTubeUploadRequest
from backend.integrations.youtube.uploader import YouTubeUploader
from backend.models.artifact import Artifact
from backend.models.publishing import PublishRecord
from backend.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


async def _load_artifact(artifact_id: str) -> Artifact | None:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Artifact).where(Artifact.id == artifact_id))
        return result.scalar_one_or_none()


async def _update_publish_record(publish_record_id: str, **fields: Any) -> None:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(PublishRecord).where(PublishRecord.id == publish_record_id))
        record = result.scalar_one_or_none()
        if record is None:
            logger.warning("PublishRecord %s not found; skipping update.", publish_record_id)
            return
        for key, value in fields.items():
            setattr(record, key, value)
        await session.commit()


@celery_app.task(bind=True, name="publish_to_youtube")
def publish_to_youtube_task(
    self,
    publish_record_id: str,
    artifact_id: str,
    account_key: str,
    title: str,
    description: str = "",
    privacy: str = "private",
) -> dict[str, Any]:
    """Download an artifact from storage and upload it to YouTube, tracking status in PublishRecord."""
    artifact = asyncio.run(_load_artifact(artifact_id))
    if artifact is None:
        asyncio.run(_update_publish_record(publish_record_id, status="failed", error_message="Artifact not found"))
        raise ValueError(f"Artifact {artifact_id} not found")

    storage = get_storage_client()
    local_path = Path("data/downloads") / Path(artifact.storage_key).name
    storage.download_file(artifact.storage_key, local_path)

    uploader = YouTubeUploader()
    request = YouTubeUploadRequest(
        file_path=str(local_path),
        title=title,
        description=description,
        privacy_status=privacy,  # type: ignore[arg-type]
    )

    asyncio.run(_update_publish_record(publish_record_id, status="uploading"))
    result = uploader.upload(account_key, request)

    if result.success:
        asyncio.run(
            _update_publish_record(
                publish_record_id,
                status="published",
                external_id=result.video_id,
                external_url=result.video_url,
            )
        )
    else:
        asyncio.run(_update_publish_record(publish_record_id, status="failed", error_message=result.error_message))

    return {
        "publish_record_id": publish_record_id,
        "success": result.success,
        "video_url": result.video_url,
        "error_message": result.error_message,
    }
