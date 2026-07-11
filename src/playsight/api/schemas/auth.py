"""Auth request/response models (CONTRACTS.md sections 6, 12)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _normalize_email(value: str) -> str:
    """Lowercase/strip an email and reject clearly malformed values."""
    email = value.strip().lower()
    if "@" not in email[1:-1] or " " in email:
        raise ValueError("value is not a valid email address")
    return email


class RegisterClubRequest(BaseModel):
    """Bootstrap: create a club plus its first admin user."""

    club_name: str = Field(min_length=1, max_length=255)
    slug: str | None = Field(default=None, max_length=255)
    email: str = Field(max_length=255)
    password: str = Field(min_length=8, max_length=255)
    full_name: str = Field(min_length=1, max_length=255)

    @field_validator("email")
    @classmethod
    def _valid_email(cls, value: str) -> str:
        return _normalize_email(value)


class LoginRequest(BaseModel):
    """Email + password credentials."""

    email: str = Field(max_length=255)
    password: str = Field(max_length=255)

    @field_validator("email")
    @classmethod
    def _valid_email(cls, value: str) -> str:
        return _normalize_email(value)


class RefreshRequest(BaseModel):
    """Refresh-token exchange (rotation: the presented token is revoked)."""

    refresh_token: str


class TokenResponse(BaseModel):
    """Access/refresh token pair."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class ClubRead(BaseModel):
    """A club (tenant)."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    slug: str
    created_at: datetime


class UserRead(BaseModel):
    """A platform user with flattened role names."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    club_id: str
    email: str
    full_name: str
    is_active: bool
    created_at: datetime
    roles: list[str] = Field(default_factory=list)

    @field_validator("roles", mode="before")
    @classmethod
    def _flatten_roles(cls, value: Any) -> Any:
        """Accept ORM ``UserRole`` rows and reduce them to role name strings."""
        if isinstance(value, list | tuple | set):
            return sorted({item.role if hasattr(item, "role") else str(item) for item in value})
        return value


class RegisterClubResponse(BaseModel):
    """Result of the register-club bootstrap: entities plus a token pair."""

    club: ClubRead
    user: UserRead
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
