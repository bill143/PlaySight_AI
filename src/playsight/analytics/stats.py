"""Per-player match statistics from tracks, identities, and events (CONTRACTS.md section 7).

All figures are honest proxies computed from bounding-box tracks:

- ``minutes_tracked``   frames the track appears in, times the processed-frame
                        period (gaps where the track is lost do not count).
- ``distance_proxy_m``  cumulative bbox-centroid displacement scaled by a
                        *nominal* pitch calibration (frame width is assumed to
                        span :data:`NOMINAL_PITCH_LENGTH_M`); per-step jumps are
                        capped at a plausible sprint speed to suppress tracking
                        teleports. This is a proxy, NOT a calibrated distance.
- event counts          joined from the rule-based events via ``track_id``.
- ``heatmap``           an 8x12 occupancy grid (rows = vertical frame bands top
                        to bottom, columns = horizontal bands left to right),
                        normalized so the cells sum to 1.0.
"""

from __future__ import annotations

from collections.abc import Sequence
from enum import Enum

import numpy as np
import pandas as pd

from playsight.analytics._tracks import estimate_frame_dt, frame_dims, normalize_tracks
from playsight.core.logging import get_logger
from playsight.core.types import (
    HEATMAP_COLS,
    HEATMAP_ROWS,
    EventSpan,
    EventType,
    IdentityResult,
    PlayerStatsRow,
    VideoInfo,
)

__all__ = ["NOMINAL_PITCH_LENGTH_M", "compute_player_stats"]

#: Nominal pitch length assumed to span the full frame width (distance proxy only).
NOMINAL_PITCH_LENGTH_M = 105.0

_MAX_PLAUSIBLE_SPEED_M_S = 11.0  # sprint cap used to suppress tracking teleports

_EVENT_FIELDS: dict[str, str] = {
    EventType.TOUCH.value: "touches",
    EventType.PASS.value: "passes",
    EventType.TACKLE.value: "tackles",
    EventType.SHOT_ATTEMPT.value: "shots",
    EventType.TURNOVER.value: "turnovers",
    EventType.SCORING_EVENT.value: "scoring_events",
}


def compute_player_stats(
    tracks_df: pd.DataFrame,
    identities: Sequence[IdentityResult],
    events: Sequence[EventSpan],
    video_info: VideoInfo,
) -> list[PlayerStatsRow]:
    """Compute per-track player statistics (one row per track id).

    Args:
        tracks_df: tracks dataframe with columns ``frame_index, t_s, track_id,
            x1, y1, x2, y2, confidence`` (CONTRACTS.md section 7).
        identities: estimated identities, joined by ``track_id`` (tracks without
            an identity get ``player_id=None`` and ``jersey_number=None``).
        events: rule-based events; per-type counts are joined by ``track_id``.
        video_info: probed video metadata (frame dimensions and fps fallbacks).

    Returns:
        One :class:`PlayerStatsRow` per track, sorted by ``track_id``. Empty
        list when the tracks dataframe has no usable rows.
    """
    df = normalize_tracks(tracks_df)
    if df is None:
        return []
    width, height = frame_dims(df, video_info)
    frame_dt = estimate_frame_dt(df, video_info)
    metres_per_px = NOMINAL_PITCH_LENGTH_M / width
    identity_by_track = {int(identity.track_id): identity for identity in identities}
    counts = _event_counts(events)

    rows: list[PlayerStatsRow] = []
    for track_id, group in df.groupby("track_id", sort=True):
        tid = int(track_id)
        identity = identity_by_track.get(tid)
        track_counts = counts.get(tid, {})
        rows.append(
            PlayerStatsRow(
                track_id=tid,
                player_id=identity.player_id if identity else None,
                jersey_number=identity.jersey_number if identity else None,
                minutes_tracked=round(len(group) * frame_dt / 60.0, 3),
                distance_proxy_m=round(_distance_proxy_m(group, metres_per_px), 1),
                touches=track_counts.get("touches", 0),
                passes=track_counts.get("passes", 0),
                tackles=track_counts.get("tackles", 0),
                shots=track_counts.get("shots", 0),
                turnovers=track_counts.get("turnovers", 0),
                scoring_events=track_counts.get("scoring_events", 0),
                avg_confidence=round(float(group["confidence"].mean()), 4),
                heatmap=_heatmap(group, width, height),
            )
        )
    get_logger(__name__).info(
        "compute_player_stats_done",
        players=len(rows),
        identified=sum(1 for row in rows if row.player_id is not None),
    )
    return rows


def _event_value(event_type: object) -> str:
    """Return the plain string value for an event type (str or EventType)."""
    return str(event_type.value) if isinstance(event_type, Enum) else str(event_type)


def _event_counts(events: Sequence[EventSpan]) -> dict[int, dict[str, int]]:
    """Count events per track id, keyed by the PlayerStatsRow field name."""
    counts: dict[int, dict[str, int]] = {}
    for event in events:
        if event.track_id is None:
            continue
        field = _EVENT_FIELDS.get(_event_value(event.event_type))
        if field is None:
            continue
        per_track = counts.setdefault(int(event.track_id), dict.fromkeys(_EVENT_FIELDS.values(), 0))
        per_track[field] += 1
    return counts


def _distance_proxy_m(group: pd.DataFrame, metres_per_px: float) -> float:
    """Cumulative centroid displacement in nominal metres, sprint-capped per step."""
    cx = group["cx"].to_numpy(dtype=np.float64)
    cy = group["cy"].to_numpy(dtype=np.float64)
    t_s = group["t_s"].to_numpy(dtype=np.float64)
    if cx.size < 2:
        return 0.0
    step_px = np.hypot(np.diff(cx), np.diff(cy))
    step_dt = np.clip(np.diff(t_s), 1e-3, None)
    cap_px = (_MAX_PLAUSIBLE_SPEED_M_S / metres_per_px) * step_dt
    return float(np.minimum(step_px, cap_px).sum() * metres_per_px)


def _heatmap(group: pd.DataFrame, width: float, height: float) -> list[list[float]]:
    """Normalized 8x12 occupancy grid of the track's centroid positions.

    Rows bin the vertical frame axis (top to bottom), columns bin the
    horizontal axis (left to right). Cells sum to 1.0 (all zeros when the
    track has no observations, which cannot happen for a grouped track).
    """
    cx = np.clip(group["cx"].to_numpy(dtype=np.float64), 0.0, width)
    cy = np.clip(group["cy"].to_numpy(dtype=np.float64), 0.0, height)
    cols = np.minimum((cx / width * HEATMAP_COLS).astype(np.int64), HEATMAP_COLS - 1)
    rows_idx = np.minimum((cy / height * HEATMAP_ROWS).astype(np.int64), HEATMAP_ROWS - 1)
    grid = np.zeros((HEATMAP_ROWS, HEATMAP_COLS), dtype=np.float64)
    np.add.at(grid, (rows_idx, cols), 1.0)
    total = float(grid.sum())
    if total > 0.0:
        grid = grid / total
    return [[round(float(value), 4) for value in row] for row in grid]
