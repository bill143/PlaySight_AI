"""Shared dataclasses and enums for the vision pipeline (CONTRACTS.md sections 7-8).

These types are the lingua franca between ingestion, detection, tracking,
identification, analytics, reporting, and the pipeline orchestrator.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

#: Heatmap grid dimensions: 8 rows (pitch length bands) x 12 columns (width bands).
HEATMAP_ROWS = 8
HEATMAP_COLS = 12


class EventType(StrEnum):
    """MVP rule-based event taxonomy (heuristic proxies, NOT ground truth)."""

    TOUCH = "touch"
    PASS = "pass"
    TACKLE = "tackle"
    SHOT_ATTEMPT = "shot_attempt"
    TURNOVER = "turnover"
    SCORING_EVENT = "scoring_event"


@dataclass
class FrameDetection:
    """One person detection in one frame (absolute pixel coordinates)."""

    frame_index: int
    t_s: float
    x1: float
    y1: float
    x2: float
    y2: float
    confidence: float


@dataclass
class TrackedBox(FrameDetection):
    """A detection associated with a persistent track id."""

    track_id: int


@dataclass
class IdentityResult:
    """Resolved (or unresolved) identity for one track."""

    track_id: int
    jersey_number: int | None
    player_id: str | None
    confidence: float
    method: str  # "ocr" | "reid" | "manual" | "unresolved"


@dataclass
class EventSpan:
    """A detected event over a time span (see EventType for the taxonomy)."""

    event_type: str  # EventType value
    t_start_s: float
    t_end_s: float
    track_id: int | None
    confidence: float
    meta: dict = field(default_factory=dict)


@dataclass
class VideoInfo:
    """Probed video metadata."""

    duration_s: float
    fps: float
    width: int
    height: int
    frame_count: int


def empty_heatmap() -> list[list[float]]:
    """Return a zeroed heatmap grid (HEATMAP_ROWS x HEATMAP_COLS)."""
    return [[0.0 for _ in range(HEATMAP_COLS)] for _ in range(HEATMAP_ROWS)]


@dataclass
class PlayerStatsRow:
    """Per-player (per-track) match statistics.

    ``heatmap`` is an 8x12 grid of floats: 8 rows, 12 columns
    (persisted as ``player_match_stats.heatmap_json``).
    """

    track_id: int
    player_id: str | None
    jersey_number: int | None
    minutes_tracked: float
    distance_proxy_m: float
    touches: int
    passes: int
    tackles: int
    shots: int
    turnovers: int
    scoring_events: int
    avg_confidence: float
    heatmap: list[list[float]] = field(default_factory=empty_heatmap)


@dataclass
class PipelineResult:
    """Result of ``pipeline.run_match_pipeline``.

    ``artifact_paths`` maps artifact kind (CONTRACTS.md section 9) to a local
    filesystem path; ``counts`` carries summary counters
    (e.g. ``{"tracks": 0, "identified": 0, "events": 0}``).
    """

    match_id: str
    artifact_paths: dict[str, str] = field(default_factory=dict)
    counts: dict[str, int] = field(default_factory=dict)
