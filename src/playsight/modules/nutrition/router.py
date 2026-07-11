"""Nutrition API router (prefix ``/nutrition``, feature flag ``nutrition``).

Mounted by the API layer under ``/api/v1``. All routes require authentication
(``get_tenant``) and the ``nutrition`` feature flag; writes additionally
require the ``admin`` or ``coach`` role. Every response schema carries
``NOT_MEDICAL_ADVICE_DISCLAIMER`` (CONTRACTS.md section 18).
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
from playsight.modules.nutrition import schemas
from playsight.modules.nutrition.models import (
    AthleteProfile,
    DayType,
    HydrationReminder,
    MealTemplate,
)
from playsight.modules.nutrition.service import NutritionService

router = APIRouter(
    prefix="/nutrition",
    tags=["nutrition"],
    dependencies=[Depends(get_tenant), Depends(require_feature("nutrition"))],
)

# Module-level singleton so route defaults contain no function calls (B008).
_require_coach = require_roles(Role.ADMIN, Role.COACH)


@router.get("/templates", response_model=list[schemas.MealTemplateRead])
def list_templates(
    day_type: DayType | None = Query(default=None),
    tenant: Any = Depends(get_tenant),
    db: Session = Depends(get_db),
) -> list[MealTemplate]:
    """List meal templates, optionally filtered by day type."""
    day_type_value = day_type.value if day_type is not None else None
    return NutritionService(db).list_templates(tenant.club_id, day_type=day_type_value)


@router.post("/templates", response_model=schemas.MealTemplateRead, status_code=201)
def create_template(
    payload: schemas.MealTemplateCreate,
    tenant: Any = Depends(get_tenant),
    db: Session = Depends(get_db),
    _user: Any = Depends(_require_coach),
) -> MealTemplate:
    """Create a meal template with macro targets."""
    return NutritionService(db).create_template(tenant.club_id, payload)


@router.get("/templates/{template_id}", response_model=schemas.MealTemplateRead)
def get_template(
    template_id: str,
    tenant: Any = Depends(get_tenant),
    db: Session = Depends(get_db),
) -> MealTemplate:
    """Fetch one meal template."""
    return NutritionService(db).get_template(tenant.club_id, template_id)


@router.delete("/templates/{template_id}", status_code=204)
def delete_template(
    template_id: str,
    tenant: Any = Depends(get_tenant),
    db: Session = Depends(get_db),
    _user: Any = Depends(_require_coach),
) -> None:
    """Delete a meal template."""
    NutritionService(db).delete_template(tenant.club_id, template_id)


@router.get("/profiles", response_model=list[schemas.ProfileRead])
def list_profiles(
    tenant: Any = Depends(get_tenant),
    db: Session = Depends(get_db),
    _user: Any = Depends(_require_coach),
) -> list[AthleteProfile]:
    """List athlete profiles (coaching staff only; contains athlete data)."""
    return NutritionService(db).list_profiles(tenant.club_id)


@router.post("/profiles", response_model=schemas.ProfileRead, status_code=201)
def create_profile(
    payload: schemas.ProfileCreate,
    tenant: Any = Depends(get_tenant),
    db: Session = Depends(get_db),
    _user: Any = Depends(_require_coach),
) -> AthleteProfile:
    """Create the nutrition profile for a player (one per player)."""
    return NutritionService(db).create_profile(tenant.club_id, payload)


@router.get("/profiles/{profile_id}", response_model=schemas.ProfileRead)
def get_profile(
    profile_id: str,
    tenant: Any = Depends(get_tenant),
    db: Session = Depends(get_db),
    _user: Any = Depends(_require_coach),
) -> AthleteProfile:
    """Fetch one athlete profile."""
    return NutritionService(db).get_profile(tenant.club_id, profile_id)


@router.patch("/profiles/{profile_id}", response_model=schemas.ProfileRead)
def update_profile(
    profile_id: str,
    payload: schemas.ProfileUpdate,
    tenant: Any = Depends(get_tenant),
    db: Session = Depends(get_db),
    _user: Any = Depends(_require_coach),
) -> AthleteProfile:
    """Apply a partial update to an athlete profile."""
    return NutritionService(db).update_profile(tenant.club_id, profile_id, payload)


@router.delete("/profiles/{profile_id}", status_code=204)
def delete_profile(
    profile_id: str,
    tenant: Any = Depends(get_tenant),
    db: Session = Depends(get_db),
    _user: Any = Depends(_require_coach),
) -> None:
    """Delete an athlete profile."""
    NutritionService(db).delete_profile(tenant.club_id, profile_id)


@router.get("/reminders", response_model=list[schemas.HydrationReminderRead])
def list_reminders(
    player_id: str | None = Query(default=None),
    tenant: Any = Depends(get_tenant),
    db: Session = Depends(get_db),
) -> list[HydrationReminder]:
    """List hydration reminders, optionally for one player."""
    return NutritionService(db).list_reminders(tenant.club_id, player_id=player_id)


@router.post("/reminders", response_model=schemas.HydrationReminderRead, status_code=201)
def create_reminder(
    payload: schemas.HydrationReminderCreate,
    tenant: Any = Depends(get_tenant),
    db: Session = Depends(get_db),
    _user: Any = Depends(_require_coach),
) -> HydrationReminder:
    """Create a hydration reminder (club-wide or bound to one player)."""
    return NutritionService(db).create_reminder(tenant.club_id, payload)


@router.patch("/reminders/{reminder_id}", response_model=schemas.HydrationReminderRead)
def update_reminder(
    reminder_id: str,
    payload: schemas.HydrationReminderUpdate,
    tenant: Any = Depends(get_tenant),
    db: Session = Depends(get_db),
    _user: Any = Depends(_require_coach),
) -> HydrationReminder:
    """Apply a partial update to a hydration reminder."""
    return NutritionService(db).update_reminder(tenant.club_id, reminder_id, payload)


@router.delete("/reminders/{reminder_id}", status_code=204)
def delete_reminder(
    reminder_id: str,
    tenant: Any = Depends(get_tenant),
    db: Session = Depends(get_db),
    _user: Any = Depends(_require_coach),
) -> None:
    """Delete a hydration reminder."""
    NutritionService(db).delete_reminder(tenant.club_id, reminder_id)


@router.get("/players/{player_id}/macro-targets")
def macro_targets(
    player_id: str,
    tenant: Any = Depends(get_tenant),
    db: Session = Depends(get_db),
    _user: Any = Depends(_require_coach),
) -> Any:
    """Macro-target recommendation (never medical advice). 501 until implemented."""
    try:
        return NutritionService(db).recommend_macro_targets(tenant.club_id, player_id)
    except NotImplementedError:
        return JSONResponse(
            status_code=501,
            content={
                "todo": "phase2",
                "docs": "docs/ROADMAP.md",
                "disclaimer": schemas.NOT_MEDICAL_ADVICE_DISCLAIMER,
            },
        )
