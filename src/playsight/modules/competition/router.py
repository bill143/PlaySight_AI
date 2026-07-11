"""Competition API router (prefix ``/competition``, feature flag ``competition``).

Mounted by the API layer under ``/api/v1``. All routes require authentication
(``get_tenant``) and the ``competition`` feature flag; writes additionally
require the ``admin`` or ``coach`` role.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from playsight.api.deps import get_tenant
from playsight.auth.rbac import Role, require_roles
from playsight.config.flags import require_feature
from playsight.db.session import get_db
from playsight.modules.competition import schemas
from playsight.modules.competition.models import Fixture, FixtureStatus, Standing
from playsight.modules.competition.service import CompetitionService

router = APIRouter(
    prefix="/competition",
    tags=["competition"],
    dependencies=[Depends(get_tenant), Depends(require_feature("competition"))],
)

# Module-level singletons so route defaults contain no function calls (B008).
_require_editor = require_roles(Role.ADMIN, Role.COACH)
_require_sync = require_roles(Role.ADMIN, Role.COACH, Role.ANALYST)


@router.get("/adapters", response_model=list[schemas.AdapterInfoRead])
def list_adapters(
    tenant: Any = Depends(get_tenant),
    db: Session = Depends(get_db),
) -> list[dict]:
    """List registered competition adapters (key, rate limit, attribution)."""
    return CompetitionService(db).list_adapters()


@router.get("/sources", response_model=list[schemas.CompetitionSourceRead])
def list_sources(
    tenant: Any = Depends(get_tenant),
    db: Session = Depends(get_db),
) -> list[Any]:
    """List the club's configured competition sources."""
    return list(CompetitionService(db).list_sources(tenant.club_id))


@router.post("/sources", response_model=schemas.CompetitionSourceRead, status_code=201)
def create_source(
    payload: schemas.CompetitionSourceCreate,
    tenant: Any = Depends(get_tenant),
    db: Session = Depends(get_db),
    _user: Any = Depends(_require_editor),
) -> Any:
    """Register a competition source for the club (validates the adapter key)."""
    return CompetitionService(db).create_source(tenant.club_id, payload)


@router.delete("/sources/{source_id}", status_code=204)
def delete_source(
    source_id: str,
    tenant: Any = Depends(get_tenant),
    db: Session = Depends(get_db),
    _user: Any = Depends(_require_editor),
) -> None:
    """Delete a source and all rows synced from it."""
    CompetitionService(db).delete_source(tenant.club_id, source_id)


@router.post("/sync", response_model=list[schemas.SyncResultRead])
def sync_all(
    tenant: Any = Depends(get_tenant),
    db: Session = Depends(get_db),
    _user: Any = Depends(_require_sync),
) -> list[Any]:
    """Sync all enabled sources for the club (change-detected via payload hash)."""
    return list(CompetitionService(db).sync(tenant.club_id))


@router.post("/sources/{source_id}/sync", response_model=list[schemas.SyncResultRead])
def sync_source(
    source_id: str,
    tenant: Any = Depends(get_tenant),
    db: Session = Depends(get_db),
    _user: Any = Depends(_require_sync),
) -> list[Any]:
    """Sync one source by id."""
    return list(CompetitionService(db).sync(tenant.club_id, source_id=source_id))


@router.get("/fixtures", response_model=list[schemas.FixtureRead])
def list_fixtures(
    status: FixtureStatus | None = Query(default=None),
    team_id: str | None = Query(default=None),
    tenant: Any = Depends(get_tenant),
    db: Session = Depends(get_db),
) -> list[Fixture]:
    """List the club's fixtures, optionally filtered by status and team."""
    status_value = status.value if status is not None else None
    return CompetitionService(db).list_fixtures(
        tenant.club_id, status=status_value, team_id=team_id
    )


@router.post("/fixtures", response_model=schemas.FixtureRead, status_code=201)
def create_fixture(
    payload: schemas.FixtureCreate,
    tenant: Any = Depends(get_tenant),
    db: Session = Depends(get_db),
    _user: Any = Depends(_require_editor),
) -> Fixture:
    """Create a manually entered fixture."""
    return CompetitionService(db).create_fixture(tenant.club_id, payload)


@router.get("/standings", response_model=list[schemas.StandingRead])
def list_standings(
    competition_name: str | None = Query(default=None),
    tenant: Any = Depends(get_tenant),
    db: Session = Depends(get_db),
) -> list[Standing]:
    """List the club's standings ordered by table position."""
    return CompetitionService(db).list_standings(tenant.club_id, competition_name=competition_name)
