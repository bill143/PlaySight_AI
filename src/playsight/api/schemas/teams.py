"""Team request/response models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class TeamCreate(BaseModel):
    """Create a team within the caller's club."""

    name: str = Field(min_length=1, max_length=255)
    sport: str = Field(min_length=1, max_length=64)
    age_group: str | None = Field(default=None, max_length=64)


class TeamRead(BaseModel):
    """A team."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    club_id: str
    name: str
    sport: str
    age_group: str | None = None
