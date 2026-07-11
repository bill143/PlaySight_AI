"""Player report endpoints (GET /players/{id}/report)."""

from __future__ import annotations

import json
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
from backend.schemas.player import PlayerReportRead, PlayerStats

router = APIRouter(prefix="/players", tags=["reports"])


@router.get("/{player_id}/report", response_model=PlayerReportRead)
async def get_player_report(
    player_id: uuid.UUID,
    db: DbSession,
    _user: User = Depends(require_permission(Permission.REPORT_READ)),
) -> PlayerReportRead:
    """Fetch the most recent generated report for a player."""
    identity_result = await db.execute(
        select(PlayerIdentity).where(PlayerIdentity.player_id == player_id).order_by(desc(PlayerIdentity.created_at))
    )
    identity = identity_result.scalars().first()
    if identity is None:
        raise NotFoundError(f"No resolved identity found for player {player_id}")

    artifact_type = f"player_report_{identity.track_id}"
    artifact_result = await db.execute(
        select(Artifact)
        .where(Artifact.match_id == identity.match_id, Artifact.artifact_type == artifact_type)
        .order_by(desc(Artifact.created_at))
    )
    artifact = artifact_result.scalars().first()
    if artifact is None:
        raise NotFoundError(f"No report artifact found for player {player_id}")

    storage = get_storage_client()
    import io

    buffer = io.BytesIO()
    storage.client.download_fileobj(storage.bucket, artifact.storage_key, buffer)
    data = json.loads(buffer.getvalue().decode("utf-8"))

    return PlayerReportRead(
        player_id=data.get("player_id", str(identity.track_id)),
        match_id=data.get("match_id", str(identity.match_id)),
        generated_at=data.get("generated_at", ""),
        stats=PlayerStats(**data.get("stats", {})),
        extra=data.get("extra", {}),
    )
