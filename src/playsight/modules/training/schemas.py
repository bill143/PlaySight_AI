"""Pydantic v2 schemas for the training module."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from playsight.modules.training.models import AttendanceStatus, PlanStatus


class TemplateCreate(BaseModel):
    """Payload to create a role-based session template."""

    name: str = Field(min_length=1, max_length=255)
    role: str = Field(default="any", min_length=1, max_length=64)
    description: str = ""
    drills_json: list[dict] = Field(default_factory=list)
    duration_minutes: int = Field(default=60, ge=1, le=600)


class TemplateRead(BaseModel):
    """A training session template."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    club_id: str
    name: str
    role: str
    description: str
    drills_json: list[dict]
    duration_minutes: int
    created_at: datetime


class PlanCreate(BaseModel):
    """Payload to create a multi-week training plan."""

    name: str = Field(min_length=1, max_length=255)
    team_id: str | None = None
    template_id: str | None = None
    starts_on: datetime | None = None
    weeks: int = Field(default=1, ge=1, le=52)
    periodization_json: dict = Field(default_factory=dict)
    status: PlanStatus = PlanStatus.DRAFT


class PlanUpdate(BaseModel):
    """Partial update of a plan (PATCH semantics)."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    team_id: str | None = None
    template_id: str | None = None
    starts_on: datetime | None = None
    weeks: int | None = Field(default=None, ge=1, le=52)
    periodization_json: dict | None = None
    status: PlanStatus | None = None


class PlanRead(BaseModel):
    """A training plan."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    club_id: str
    team_id: str | None
    template_id: str | None
    name: str
    starts_on: datetime | None
    weeks: int
    periodization_json: dict
    status: PlanStatus
    created_at: datetime


class AttendanceCreate(BaseModel):
    """Payload to record one player's attendance at one session."""

    player_id: str = Field(min_length=1, max_length=32)
    session_at: datetime
    status: AttendanceStatus = AttendanceStatus.PRESENT
    note: str | None = Field(default=None, max_length=512)


class AttendanceRead(BaseModel):
    """An attendance record."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    club_id: str
    plan_id: str
    player_id: str
    session_at: datetime
    status: AttendanceStatus
    note: str | None
    created_at: datetime


class CoachNoteCreate(BaseModel):
    """Payload to add a coach note about a player."""

    player_id: str = Field(min_length=1, max_length=32)
    note: str = Field(min_length=1)
    plan_id: str | None = None
    visibility: str = Field(default="coaches", pattern="^(coaches|player)$")


class CoachNoteRead(BaseModel):
    """A coach note."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    club_id: str
    player_id: str
    plan_id: str | None
    author_user_id: str | None
    note: str
    visibility: str
    created_at: datetime
