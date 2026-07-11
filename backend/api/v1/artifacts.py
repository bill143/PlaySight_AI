"""Artifact download endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select

from backend.api.deps import DbSession, require_permission
from backend.core.exceptions import NotFoundError
from backend.core.rbac import Permission
from backend.core.storage import get_storage_client
from backend.models.artifact import Artifact
from backend.models.user import User
from backend.schemas.artifact import ArtifactDownloadResponse

router = APIRouter(prefix="/artifacts", tags=["artifacts"])


@router.get("/{artifact_id}/download", response_model=ArtifactDownloadResponse)
async def download_artifact(
    artifact_id: uuid.UUID,
    db: DbSession,
    _user: User = Depends(require_permission(Permission.ARTIFACT_DOWNLOAD)),
) -> ArtifactDownloadResponse:
    """Generate a presigned download URL for any artifact (report, video, export)."""
    result = await db.execute(select(Artifact).where(Artifact.id == artifact_id))
    artifact = result.scalar_one_or_none()
    if artifact is None:
        raise NotFoundError(f"Artifact {artifact_id} not found")

    storage = get_storage_client()
    download_url = storage.generate_presigned_url(artifact.storage_key)

    return ArtifactDownloadResponse(artifact_id=artifact.id, download_url=download_url)
