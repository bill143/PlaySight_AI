"""Player endpoints (reads: any authenticated user; writes: admin|coach)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from playsight.api.deps import Pagination, TenantContext, get_db, get_tenant, pagination_params
from playsight.api.schemas.players import PlayerCreate, PlayerRead
from playsight.auth.rbac import Role, require_roles
from playsight.core.errors import NotFoundError
from playsight.db.models import Player, Team

router = APIRouter(prefix="/players", tags=["players"])

_require_writer = require_roles(Role.ADMIN, Role.COACH)


@router.get("", response_model=list[PlayerRead])
def list_players(
    team_id: str | None = Query(default=None, description="Filter by team."),
    tenant: TenantContext = Depends(get_tenant),
    db: Session = Depends(get_db),
    page: Pagination = Depends(pagination_params),
) -> list[Player]:
    """List the club's players, optionally filtered by team."""
    query = db.query(Player).filter(Player.club_id == tenant.club_id)
    if team_id is not None:
        query = query.filter(Player.team_id == team_id)
    return query.order_by(Player.full_name).offset(page.offset).limit(page.limit).all()


@router.post("", response_model=PlayerRead, status_code=201)
def create_player(
    payload: PlayerCreate,
    tenant: TenantContext = Depends(get_tenant),
    db: Session = Depends(get_db),
    _user: Any = Depends(_require_writer),
) -> Player:
    """Create a player on one of the club's teams."""
    team = db.get(Team, payload.team_id)
    if team is None or team.club_id != tenant.club_id:
        raise NotFoundError(f"Team not found: {payload.team_id}")
    player = Player(
        club_id=tenant.club_id,
        team_id=payload.team_id,
        full_name=payload.full_name,
        jersey_number=payload.jersey_number,
        position=payload.position,
        external_ref=payload.external_ref,
    )
    db.add(player)
    db.commit()
    db.refresh(player)
    return player
