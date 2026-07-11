"""Pydantic v2 schemas for the registration module (Phase 3 scaffold)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from playsight.modules.registration.models import RegistrantType, RegistrationStatus


class RegistrationFormCreate(BaseModel):
    """Payload to create a configurable registration form."""

    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    season: str | None = Field(default=None, max_length=64)
    fields_json: list[dict[str, Any]] = Field(default_factory=list)
    is_active: bool = True


class RegistrationFormRead(BaseModel):
    """A registration form as returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    club_id: str
    name: str
    description: str | None
    season: str | None
    fields_json: list[dict[str, Any]]
    is_active: bool
    created_at: datetime


class RegistrationCreate(BaseModel):
    """Payload to create a registration (starts in ``draft``)."""

    form_id: str | None = None
    registrant_type: RegistrantType = RegistrantType.PLAYER
    registrant_name: str = Field(min_length=1, max_length=255)
    registrant_dob: date | None = None
    family_group_id: str | None = Field(default=None, max_length=32)
    answers_json: dict[str, Any] = Field(default_factory=dict)
    consent_json: dict[str, Any] = Field(default_factory=dict)
    medical_flags_json: dict[str, Any] = Field(default_factory=dict)


class RegistrationRead(BaseModel):
    """A registration as returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    club_id: str
    form_id: str | None
    user_id: str | None
    registrant_type: RegistrantType
    registrant_name: str
    registrant_dob: date | None
    family_group_id: str | None
    status: RegistrationStatus
    answers_json: dict[str, Any]
    consent_json: dict[str, Any]
    medical_flags_json: dict[str, Any]
    submitted_at: datetime | None
    decided_at: datetime | None
    decided_by: str | None
    created_at: datetime
    updated_at: datetime


class RegistrationStatusUpdate(BaseModel):
    """Payload for a registrar decision / workflow transition."""

    status: RegistrationStatus


class RegistrationDocumentRead(BaseModel):
    """A registration document record as returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    club_id: str
    registration_id: str
    storage_key: str
    doc_type: str
    filename: str
    content_type: str
    uploaded_by: str | None
    created_at: datetime
