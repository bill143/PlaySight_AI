"""Player-related Pydantic schemas."""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict


class PlayerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    full_name: str
    jersey_number: int | None = None
    position: str | None = None


class PlayerStats(BaseModel):
    jersey_number: int | None = None
    distance_covered_m: float = 0.0
    top_speed_kmh: float = 0.0
    possessions: int = 0
    passes: int = 0
    shots: int = 0
    goals: int = 0
    time_on_ball_seconds: float = 0.0
    heatmap_zones: dict[str, float] = {}


class PlayerReportRead(BaseModel):
    player_id: str
    match_id: str
    generated_at: str
    stats: PlayerStats
    extra: dict[str, Any] = {}


class PlayerHighlightRead(BaseModel):
    player_id: str
    match_id: str
    artifact_id: uuid.UUID | None = None
    download_url: str | None = None
    clip_count: int = 0
