"""Team endpoints (reads: any authenticated user; writes: admin|coach)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from playsight.api.deps import Pagination, TenantContext, get_db, get_tenant, pagination_params
from playsight.api.schemas.teams import TeamCreate, TeamRead
from playsight.auth.rbac import Role, require_roles
from playsight.db.models import Team

router = APIRouter(prefix="/teams", tags=["teams"])

_require_writer = require_roles(Role.ADMIN, Role.COACH)


@router.get("", response_model=list[TeamRead])
def list_teams(
    tenant: TenantContext = Depends(get_tenant),
    db: Session = Depends(get_db),
    page: Pagination = Depends(pagination_params),
) -> list[Team]:
    """List the club's teams."""
    return (
        db.query(Team)
        .filter(Team.club_id == tenant.club_id)
        .order_by(Team.name)
        .offset(page.offset)
        .limit(page.limit)
        .all()
    )


@router.post("", response_model=TeamRead, status_code=201)
def create_team(
    payload: TeamCreate,
    tenant: TenantContext = Depends(get_tenant),
    db: Session = Depends(get_db),
    _user: Any = Depends(_require_writer),
) -> Team:
    """Create a team in the caller's club."""
    team = Team(
        club_id=tenant.club_id,
        name=payload.name,
        sport=payload.sport,
        age_group=payload.age_group,
    )
    db.add(team)
    db.commit()
    db.refresh(team)
    return team
