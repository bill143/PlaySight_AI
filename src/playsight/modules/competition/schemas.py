"""Pydantic v2 schemas for the competition module."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from playsight.modules.competition.models import FixtureStatus


class CompetitionSourceCreate(BaseModel):
    """Payload to register a competition data source for a club."""

    name: str = Field(min_length=1, max_length=255)
    adapter_key: str = Field(min_length=1, max_length=64)
    config_json: dict = Field(default_factory=dict)
    enabled: bool = True


class CompetitionSourceRead(BaseModel):
    """A configured competition source."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    club_id: str
    name: str
    adapter_key: str
    config_json: dict
    attribution: str
    enabled: bool
    last_synced_at: datetime | None
    last_sync_hash: str | None
    created_at: datetime


class FixtureCreate(BaseModel):
    """Payload to create a fixture manually (no external source)."""

    home_team: str = Field(min_length=1, max_length=255)
    away_team: str = Field(min_length=1, max_length=255)
    kickoff_at: datetime | None = None
    venue: str | None = None
    competition_name: str | None = None
    status: FixtureStatus = FixtureStatus.SCHEDULED
    home_score: int | None = None
    away_score: int | None = None
    team_id: str | None = None
    external_ref: str | None = None


class FixtureRead(BaseModel):
    """A fixture row (synced or manual)."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    club_id: str
    source_id: str | None
    team_id: str | None
    external_ref: str | None
    competition_name: str | None
    home_team: str
    away_team: str
    kickoff_at: datetime | None
    venue: str | None
    status: FixtureStatus
    home_score: int | None
    away_score: int | None
    content_hash: str | None
    created_at: datetime
    updated_at: datetime


class StandingRead(BaseModel):
    """A league-table row."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    club_id: str
    source_id: str | None
    competition_name: str | None
    season: str | None
    team_name: str
    position: int
    played: int
    won: int
    drawn: int
    lost: int
    goals_for: int
    goals_against: int
    points: int
    content_hash: str | None
    updated_at: datetime


class SyncResultRead(BaseModel):
    """Outcome of syncing one competition source."""

    model_config = ConfigDict(from_attributes=True)

    source_id: str
    adapter_key: str
    changed: bool
    fixtures_upserted: int
    standings_upserted: int
    sync_hash: str
    attribution: str


class AdapterInfoRead(BaseModel):
    """Metadata about a registered competition adapter."""

    key: str
    rate_limit_per_minute: int
    attribution: str
