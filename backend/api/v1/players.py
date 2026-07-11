"""Player CRUD/read endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select

from backend.api.deps import DbSession, require_permission
from backend.core.exceptions import NotFoundError
from backend.core.rbac import Permission
from backend.models.player import Player
from backend.models.user import User
from backend.schemas.player import PlayerRead

router = APIRouter(prefix="/players", tags=["players"])


@router.get("", response_model=list[PlayerRead])
async def list_players(
    db: DbSession,
    limit: int = 100,
    offset: int = 0,
    _user: User = Depends(require_permission(Permission.PLAYER_READ)),
) -> list[Player]:
    """List known players."""
    result = await db.execute(select(Player).order_by(Player.full_name).offset(offset).limit(limit))
    return list(result.scalars().all())


@router.get("/{player_id}", response_model=PlayerRead)
async def get_player(
    player_id: uuid.UUID,
    db: DbSession,
    _user: User = Depends(require_permission(Permission.PLAYER_READ)),
) -> Player:
    """Get a single player's profile."""
    result = await db.execute(select(Player).where(Player.id == player_id))
    player = result.scalar_one_or_none()
    if player is None:
        raise NotFoundError(f"Player {player_id} not found")
    return player
