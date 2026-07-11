"""Player highlight endpoints (GET /players/{id}/highlights)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import desc, select

from backend.api.deps import DbSession, require_permission
from backend.core.exceptions import NotFoundError
from backend.core.rbac import Permission
from backend.core.storage import get_storage_client
from backend.models.artifact import Artifact
from backend.models.player import PlayerIdentity
from backend.models.user import User
from backend.schemas.player import PlayerHighlightRead

router = APIRouter(prefix="/players", tags=["highlights"])


@router.get("/{player_id}/highlights", response_model=PlayerHighlightRead)
async def get_player_highlights(
    player_id: uuid.UUID,
    db: DbSession,
    _user: User = Depends(require_permission(Permission.HIGHLIGHT_READ)),
) -> PlayerHighlightRead:
    """Fetch the most recent highlight reel artifact for a player."""
    identity_result = await db.execute(
        select(PlayerIdentity).where(PlayerIdentity.player_id == player_id).order_by(desc(PlayerIdentity.created_at))
    )
    identity = identity_result.scalars().first()
    if identity is None:
        raise NotFoundError(f"No resolved identity found for player {player_id}")

    artifact_type = f"player_highlights_{identity.track_id}"
    artifact_result = await db.execute(
        select(Artifact)
        .where(Artifact.match_id == identity.match_id, Artifact.artifact_type == artifact_type)
        .order_by(desc(Artifact.created_at))
    )
    artifact = artifact_result.scalars().first()

    download_url = None
    if artifact is not None:
        storage = get_storage_client()
        download_url = storage.generate_presigned_url(artifact.storage_key)

    return PlayerHighlightRead(
        player_id=str(player_id),
        match_id=str(identity.match_id),
        artifact_id=artifact.id if artifact else None,
        download_url=download_url,
        clip_count=1 if artifact else 0,
    )
