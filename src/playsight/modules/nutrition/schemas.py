"""Pydantic v2 schemas for the nutrition module.

Per CONTRACTS.md section 18, every response schema carries
``NOT_MEDICAL_ADVICE_DISCLAIMER`` in a ``disclaimer`` field.
"""

from __future__ import annotations

from datetime import datetime
from typing import Final

from pydantic import BaseModel, ConfigDict, Field

from playsight.modules.nutrition.models import DayType, UnitsPreference

#: Mandatory disclaimer on every nutrition module output (CONTRACTS.md §18).
NOT_MEDICAL_ADVICE_DISCLAIMER: Final[str] = (
    "This information is general guidance for sports-club operations only. "
    "It is not medical, dietetic, or health advice. Consult a qualified "
    "professional before changing an athlete's diet, hydration, or supplementation."
)

_TIME_OF_DAY_PATTERN = r"^([01]\d|2[0-3]):[0-5]\d$"


class ProfileCreate(BaseModel):
    """Payload to create an athlete nutrition profile."""

    player_id: str = Field(min_length=1, max_length=32)
    units: UnitsPreference = UnitsPreference.METRIC
    height_cm: float | None = Field(default=None, gt=0, lt=300)
    weight_kg: float | None = Field(default=None, gt=0, lt=400)
    dietary_flags_json: list[str] = Field(default_factory=list)


class ProfileUpdate(BaseModel):
    """Partial update of an athlete profile (PATCH semantics)."""

    units: UnitsPreference | None = None
    height_cm: float | None = Field(default=None, gt=0, lt=300)
    weight_kg: float | None = Field(default=None, gt=0, lt=400)
    dietary_flags_json: list[str] | None = None


class ProfileRead(BaseModel):
    """An athlete nutrition profile (carries the mandatory disclaimer)."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    club_id: str
    player_id: str
    units: UnitsPreference
    height_cm: float | None
    weight_kg: float | None
    dietary_flags_json: list[str]
    created_at: datetime
    updated_at: datetime
    disclaimer: str = NOT_MEDICAL_ADVICE_DISCLAIMER


class MealTemplateCreate(BaseModel):
    """Payload to create a meal template with macro targets."""

    name: str = Field(min_length=1, max_length=255)
    day_type: DayType
    description: str = ""
    macros_json: dict = Field(
        default_factory=dict,
        description='e.g. {"kcal": 2600, "protein_g": 140, "carbs_g": 320, "fat_g": 70}',
    )


class MealTemplateRead(BaseModel):
    """A meal template (carries the mandatory disclaimer)."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    club_id: str
    name: str
    day_type: DayType
    description: str
    macros_json: dict
    created_at: datetime
    disclaimer: str = NOT_MEDICAL_ADVICE_DISCLAIMER


class HydrationReminderCreate(BaseModel):
    """Payload to create a hydration reminder."""

    label: str = Field(default="Drink water", min_length=1, max_length=255)
    time_of_day: str = Field(default="09:00", pattern=_TIME_OF_DAY_PATTERN)
    interval_minutes: int | None = Field(default=None, ge=5, le=1440)
    player_id: str | None = None
    enabled: bool = True


class HydrationReminderUpdate(BaseModel):
    """Partial update of a hydration reminder (PATCH semantics)."""

    label: str | None = Field(default=None, min_length=1, max_length=255)
    time_of_day: str | None = Field(default=None, pattern=_TIME_OF_DAY_PATTERN)
    interval_minutes: int | None = Field(default=None, ge=5, le=1440)
    enabled: bool | None = None


class HydrationReminderRead(BaseModel):
    """A hydration reminder (carries the mandatory disclaimer)."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    club_id: str
    player_id: str | None
    label: str
    time_of_day: str
    interval_minutes: int | None
    enabled: bool
    created_at: datetime
    disclaimer: str = NOT_MEDICAL_ADVICE_DISCLAIMER
