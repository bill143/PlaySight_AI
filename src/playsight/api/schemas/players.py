"""Player request/response models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class PlayerCreate(BaseModel):
    """Create a rostered player on a team of the caller's club."""

    team_id: str
    full_name: str = Field(min_length=1, max_length=255)
    jersey_number: int | None = Field(default=None, ge=0, le=999)
    position: str | None = Field(default=None, max_length=64)
    external_ref: str | None = Field(default=None, max_length=255)


class PlayerRead(BaseModel):
    """A rostered player."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    club_id: str
    team_id: str
    full_name: str
    jersey_number: int | None = None
    position: str | None = None
    external_ref: str | None = None
