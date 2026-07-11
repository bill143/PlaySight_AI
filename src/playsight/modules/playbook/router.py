"""Playbook API router (prefix ``/playbook``, feature flag ``playbook``).

Mounted by the API layer under ``/api/v1``. All routes require authentication
(``get_tenant``) and the ``playbook`` feature flag; writes additionally
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
from playsight.modules.playbook import schemas
from playsight.modules.playbook.models import Play, PlayAssignment, PlayCategory, PlayClipLink
from playsight.modules.playbook.service import PlaybookService

router = APIRouter(
    prefix="/playbook",
    tags=["playbook"],
    dependencies=[Depends(get_tenant), Depends(require_feature("playbook"))],
)

# Module-level singleton so route defaults contain no function calls (B008).
_require_coach = require_roles(Role.ADMIN, Role.COACH)


@router.get("/plays", response_model=list[schemas.PlayRead])
def list_plays(
    category: PlayCategory | None = Query(default=None),
    team_id: str | None = Query(default=None),
    tag: str | None = Query(default=None, description="Case-insensitive tag filter"),
    latest_only: bool = Query(default=True, description="Hide superseded versions"),
    tenant: Any = Depends(get_tenant),
    db: Session = Depends(get_db),
) -> list[Play]:
    """List plays with optional category/team/tag filters (search-by-tag)."""
    category_value = category.value if category is not None else None
    return PlaybookService(db).list_plays(
        tenant.club_id,
        category=category_value,
        team_id=team_id,
        tag=tag,
        latest_only=latest_only,
    )


@router.post("/plays", response_model=schemas.PlayRead, status_code=201)
def create_play(
    payload: schemas.PlayCreate,
    tenant: Any = Depends(get_tenant),
    db: Session = Depends(get_db),
    _user: Any = Depends(_require_coach),
) -> Play:
    """Create version 1 of a new play."""
    return PlaybookService(db).create_play(tenant.club_id, payload)


@router.get("/plays/{play_id}", response_model=schemas.PlayRead)
def get_play(
    play_id: str,
    tenant: Any = Depends(get_tenant),
    db: Session = Depends(get_db),
) -> Play:
    """Fetch one play version."""
    return PlaybookService(db).get_play(tenant.club_id, play_id)


@router.post("/plays/{play_id}/revisions", response_model=schemas.PlayRead, status_code=201)
def revise_play(
    play_id: str,
    payload: schemas.PlayRevisionCreate,
    tenant: Any = Depends(get_tenant),
    db: Session = Depends(get_db),
    _user: Any = Depends(_require_coach),
) -> Play:
    """Create a new version of a play (unset fields inherit from the parent)."""
    return PlaybookService(db).revise_play(tenant.club_id, play_id, payload)


@router.get("/plays/{play_id}/versions", response_model=list[schemas.PlayRead])
def list_versions(
    play_id: str,
    tenant: Any = Depends(get_tenant),
    db: Session = Depends(get_db),
) -> list[Play]:
    """Return the full version history of a play, oldest first."""
    return PlaybookService(db).list_versions(tenant.club_id, play_id)


@router.delete("/plays/{play_id}", status_code=204)
def delete_play(
    play_id: str,
    tenant: Any = Depends(get_tenant),
    db: Session = Depends(get_db),
    _user: Any = Depends(_require_coach),
) -> None:
    """Delete one play version with its assignments and clip links."""
    PlaybookService(db).delete_play(tenant.club_id, play_id)


@router.post("/plays/{play_id}/assignments", response_model=schemas.AssignmentRead, status_code=201)
def add_assignment(
    play_id: str,
    payload: schemas.AssignmentCreate,
    tenant: Any = Depends(get_tenant),
    db: Session = Depends(get_db),
    _user: Any = Depends(_require_coach),
) -> PlayAssignment:
    """Attach a role/player responsibility to a play."""
    return PlaybookService(db).add_assignment(tenant.club_id, play_id, payload)


@router.get("/plays/{play_id}/assignments", response_model=list[schemas.AssignmentRead])
def list_assignments(
    play_id: str,
    tenant: Any = Depends(get_tenant),
    db: Session = Depends(get_db),
) -> list[PlayAssignment]:
    """List the assignments of a play."""
    return PlaybookService(db).list_assignments(tenant.club_id, play_id)


@router.delete("/assignments/{assignment_id}", status_code=204)
def remove_assignment(
    assignment_id: str,
    tenant: Any = Depends(get_tenant),
    db: Session = Depends(get_db),
    _user: Any = Depends(_require_coach),
) -> None:
    """Remove one assignment."""
    PlaybookService(db).remove_assignment(tenant.club_id, assignment_id)


@router.post("/plays/{play_id}/clips", response_model=schemas.ClipLinkRead, status_code=201)
def add_clip_link(
    play_id: str,
    payload: schemas.ClipLinkCreate,
    tenant: Any = Depends(get_tenant),
    db: Session = Depends(get_db),
    _user: Any = Depends(_require_coach),
) -> PlayClipLink:
    """Link a play to a detected match event."""
    return PlaybookService(db).add_clip_link(tenant.club_id, play_id, payload)


@router.get("/plays/{play_id}/clips", response_model=list[schemas.ClipLinkRead])
def list_clip_links(
    play_id: str,
    tenant: Any = Depends(get_tenant),
    db: Session = Depends(get_db),
) -> list[PlayClipLink]:
    """List the clip links of a play."""
    return PlaybookService(db).list_clip_links(tenant.club_id, play_id)


@router.delete("/clips/{link_id}", status_code=204)
def remove_clip_link(
    link_id: str,
    tenant: Any = Depends(get_tenant),
    db: Session = Depends(get_db),
    _user: Any = Depends(_require_coach),
) -> None:
    """Remove one clip link."""
    PlaybookService(db).remove_clip_link(tenant.club_id, link_id)
