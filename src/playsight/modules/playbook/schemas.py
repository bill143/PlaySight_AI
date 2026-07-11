"""Pydantic v2 schemas for the playbook module."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from playsight.modules.playbook.models import PlayCategory


class PlayCreate(BaseModel):
    """Payload to create the first version of a play."""

    title: str = Field(min_length=1, max_length=255)
    category: PlayCategory
    notes: str = ""
    team_id: str | None = None
    diagram_storage_key: str | None = None
    tags_json: list[str] = Field(default_factory=list)


class PlayRevisionCreate(BaseModel):
    """Payload to create a new version of a play (unset fields are inherited)."""

    title: str | None = Field(default=None, min_length=1, max_length=255)
    category: PlayCategory | None = None
    notes: str | None = None
    team_id: str | None = None
    diagram_storage_key: str | None = None
    tags_json: list[str] | None = None


class PlayRead(BaseModel):
    """One version of a play."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    club_id: str
    team_id: str | None
    category: PlayCategory
    title: str
    notes: str
    diagram_storage_key: str | None
    version: int
    parent_play_id: str | None
    tags_json: list[str]
    created_at: datetime
    updated_at: datetime


class AssignmentCreate(BaseModel):
    """Payload to add a role/player responsibility to a play."""

    role: str = Field(min_length=1, max_length=64)
    instructions: str = ""
    player_id: str | None = None


class AssignmentRead(BaseModel):
    """A play assignment."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    club_id: str
    play_id: str
    player_id: str | None
    role: str
    instructions: str
    created_at: datetime


class ClipLinkCreate(BaseModel):
    """Payload to link a play to a detected match event."""

    match_event_id: str = Field(min_length=1, max_length=32)
    note: str | None = Field(default=None, max_length=512)


class ClipLinkRead(BaseModel):
    """A play-to-match-event clip link."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    club_id: str
    play_id: str
    match_event_id: str
    note: str | None
    created_at: datetime
