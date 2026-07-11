"""Match, video, event, and stats models (CONTRACTS.md sections 5, 8, 12)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class MatchCreate(BaseModel):
    """Create a match for one of the club's teams."""

    team_id: str
    opponent: str = Field(min_length=1, max_length=255)
    sport: str = Field(min_length=1, max_length=64)
    kickoff_at: datetime | None = None
    venue: str | None = Field(default=None, max_length=255)
    period_config: dict[str, Any] | None = Field(
        default=None,
        description='Period layout, e.g. {"periods": 2, "period_minutes": 45}.',
    )


class MatchRead(BaseModel):
    """A match."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    club_id: str
    team_id: str
    opponent: str
    sport: str
    kickoff_at: datetime | None = None
    venue: str | None = None
    period_config: dict[str, Any] = Field(
        default_factory=dict, validation_alias="period_config_json"
    )
    status: str
    created_at: datetime


class VideoSourceRequest(BaseModel):
    """JSON alternative to a multipart upload: a server-local video path."""

    source_path: str = Field(min_length=1)


class VideoAssetRead(BaseModel):
    """An ingested match video."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    club_id: str
    match_id: str
    storage_key: str
    filename: str
    duration_s: float
    fps: float
    width: int
    height: int
    status: str
    meta: dict[str, Any] = Field(default_factory=dict, validation_alias="meta_json")


class HighlightsRequest(BaseModel):
    """Target of a highlights job: a resolved identity or a raw track id."""

    player_identity_id: str | None = None
    track_id: int | None = None

    @model_validator(mode="after")
    def _one_target(self) -> HighlightsRequest:
        if self.player_identity_id is None and self.track_id is None:
            raise ValueError("Provide 'player_identity_id' or 'track_id'.")
        return self


class PlayerIdentityRead(BaseModel):
    """Estimated (confidence-scored) identity for one track."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    match_id: str
    track_id: int
    player_id: str | None = None
    jersey_number: int | None = None
    confidence: float
    method: str


class MatchEventRead(BaseModel):
    """One heuristic event span (MVP proxies, not ground truth)."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    match_id: str
    event_type: str
    t_start_s: float
    t_end_s: float
    player_identity_id: str | None = None
    track_id: int | None = None
    confidence: float
    meta: dict[str, Any] = Field(default_factory=dict, validation_alias="meta_json")


class PlayerStatsRead(BaseModel):
    """Aggregated per-player statistics for one match."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    match_id: str
    player_identity_id: str
    minutes_tracked: float
    distance_proxy_m: float
    touches: int
    passes: int
    tackles: int
    shots: int
    turnovers: int
    scoring_events: int
    avg_confidence: float
    heatmap: list[list[float]] = Field(default_factory=list, validation_alias="heatmap_json")
    identity: PlayerIdentityRead | None = None
