"""Training API router (prefix ``/training``, feature flag ``training``).

Mounted by the API layer under ``/api/v1``. All routes require authentication
(``get_tenant``) and the ``training`` feature flag; writes additionally
require the ``admin`` or ``coach`` role.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from playsight.api.deps import get_tenant
from playsight.auth.rbac import Role, require_roles
from playsight.config.flags import require_feature
from playsight.db.session import get_db
from playsight.modules.training import schemas
from playsight.modules.training.models import (
    Attendance,
    CoachNote,
    PlanStatus,
    TrainingPlan,
    TrainingTemplate,
)
from playsight.modules.training.service import TrainingService

router = APIRouter(
    prefix="/training",
    tags=["training"],
    dependencies=[Depends(get_tenant), Depends(require_feature("training"))],
)

# Module-level singletons so route defaults contain no function calls (B008).
_require_coach = require_roles(Role.ADMIN, Role.COACH)
_require_staff = require_roles(Role.ADMIN, Role.COACH, Role.ANALYST)


@router.get("/templates", response_model=list[schemas.TemplateRead])
def list_templates(
    role: str | None = Query(default=None),
    tenant: Any = Depends(get_tenant),
    db: Session = Depends(get_db),
) -> list[TrainingTemplate]:
    """List session templates, optionally filtered by target role."""
    return TrainingService(db).list_templates(tenant.club_id, role=role)


@router.post("/templates", response_model=schemas.TemplateRead, status_code=201)
def create_template(
    payload: schemas.TemplateCreate,
    tenant: Any = Depends(get_tenant),
    db: Session = Depends(get_db),
    _user: Any = Depends(_require_coach),
) -> TrainingTemplate:
    """Create a role-based session template."""
    return TrainingService(db).create_template(tenant.club_id, payload)


@router.delete("/templates/{template_id}", status_code=204)
def delete_template(
    template_id: str,
    tenant: Any = Depends(get_tenant),
    db: Session = Depends(get_db),
    _user: Any = Depends(_require_coach),
) -> None:
    """Delete a template (plans keep existing with the reference nulled)."""
    TrainingService(db).delete_template(tenant.club_id, template_id)


@router.get("/plans", response_model=list[schemas.PlanRead])
def list_plans(
    status: PlanStatus | None = Query(default=None),
    team_id: str | None = Query(default=None),
    tenant: Any = Depends(get_tenant),
    db: Session = Depends(get_db),
) -> list[TrainingPlan]:
    """List training plans, optionally filtered by status and team."""
    status_value = status.value if status is not None else None
    return TrainingService(db).list_plans(tenant.club_id, status=status_value, team_id=team_id)


@router.post("/plans", response_model=schemas.PlanRead, status_code=201)
def create_plan(
    payload: schemas.PlanCreate,
    tenant: Any = Depends(get_tenant),
    db: Session = Depends(get_db),
    _user: Any = Depends(_require_coach),
) -> TrainingPlan:
    """Create a multi-week plan with week periodization JSON."""
    return TrainingService(db).create_plan(tenant.club_id, payload)


@router.get("/plans/{plan_id}", response_model=schemas.PlanRead)
def get_plan(
    plan_id: str,
    tenant: Any = Depends(get_tenant),
    db: Session = Depends(get_db),
) -> TrainingPlan:
    """Fetch one training plan."""
    return TrainingService(db).get_plan(tenant.club_id, plan_id)


@router.patch("/plans/{plan_id}", response_model=schemas.PlanRead)
def update_plan(
    plan_id: str,
    payload: schemas.PlanUpdate,
    tenant: Any = Depends(get_tenant),
    db: Session = Depends(get_db),
    _user: Any = Depends(_require_coach),
) -> TrainingPlan:
    """Apply a partial update to a plan."""
    return TrainingService(db).update_plan(tenant.club_id, plan_id, payload)


@router.delete("/plans/{plan_id}", status_code=204)
def delete_plan(
    plan_id: str,
    tenant: Any = Depends(get_tenant),
    db: Session = Depends(get_db),
    _user: Any = Depends(_require_coach),
) -> None:
    """Delete a plan together with its attendance records."""
    TrainingService(db).delete_plan(tenant.club_id, plan_id)


@router.post("/plans/{plan_id}/attendance", response_model=schemas.AttendanceRead, status_code=201)
def record_attendance(
    plan_id: str,
    payload: schemas.AttendanceCreate,
    tenant: Any = Depends(get_tenant),
    db: Session = Depends(get_db),
    _user: Any = Depends(_require_coach),
) -> Attendance:
    """Record one player's attendance for one session of a plan."""
    return TrainingService(db).record_attendance(tenant.club_id, plan_id, payload)


@router.get("/plans/{plan_id}/attendance", response_model=list[schemas.AttendanceRead])
def list_attendance(
    plan_id: str,
    player_id: str | None = Query(default=None),
    tenant: Any = Depends(get_tenant),
    db: Session = Depends(get_db),
) -> list[Attendance]:
    """List attendance records of a plan, optionally for one player."""
    return TrainingService(db).list_attendance(tenant.club_id, plan_id, player_id=player_id)


@router.post("/notes", response_model=schemas.CoachNoteRead, status_code=201)
def add_note(
    payload: schemas.CoachNoteCreate,
    tenant: Any = Depends(get_tenant),
    db: Session = Depends(get_db),
    user: Any = Depends(_require_coach),
) -> CoachNote:
    """Add a coach note about a player (author = current user)."""
    author_id = getattr(user, "id", None)
    return TrainingService(db).add_note(tenant.club_id, payload, author_user_id=author_id)


@router.get("/notes", response_model=list[schemas.CoachNoteRead])
def list_notes(
    player_id: str | None = Query(default=None),
    tenant: Any = Depends(get_tenant),
    db: Session = Depends(get_db),
    _user: Any = Depends(_require_staff),
) -> list[CoachNote]:
    """List coach notes, optionally for one player (coaching staff only)."""
    return TrainingService(db).list_notes(tenant.club_id, player_id=player_id)


@router.delete("/notes/{note_id}", status_code=204)
def delete_note(
    note_id: str,
    tenant: Any = Depends(get_tenant),
    db: Session = Depends(get_db),
    _user: Any = Depends(_require_coach),
) -> None:
    """Delete one coach note."""
    TrainingService(db).delete_note(tenant.club_id, note_id)


@router.get("/players/{player_id}/workload")
def player_workload(
    player_id: str,
    tenant: Any = Depends(get_tenant),
    db: Session = Depends(get_db),
    _user: Any = Depends(_require_staff),
) -> Any:
    """Workload recommendation from player_match_stats. 501 until implemented."""
    try:
        return TrainingService(db).recommend_workload(tenant.club_id, player_id)
    except NotImplementedError:
        return JSONResponse(status_code=501, content={"todo": "phase2", "docs": "docs/ROADMAP.md"})
