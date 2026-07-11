"""Match, video, and processing job Pydantic schemas."""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict


class MatchMetadataIn(BaseModel):
    home_team: str = ""
    away_team: str = ""
    match_date: str = ""
    sport: str = "football"
    extra: dict[str, Any] = {}


class MatchCreate(BaseModel):
    title: str
    sport: str = "football"
    home_team: str = ""
    away_team: str = ""
    match_date: str = ""
    club_id: uuid.UUID | None = None


class MatchRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    sport: str
    home_team: str
    away_team: str
    match_date: str
    status: str


class MatchIngestResponse(BaseModel):
    match_id: uuid.UUID
    job_id: uuid.UUID
    status: str


class VideoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    match_id: uuid.UUID
    original_filename: str
    duration_seconds: float | None = None
    fps: float | None = None
