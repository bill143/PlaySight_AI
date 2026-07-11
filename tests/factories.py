"""Deterministic builders for synthetic analytics inputs used by unit tests."""

from __future__ import annotations

import pandas as pd

from playsight.core.types import EventSpan, IdentityResult, PlayerStatsRow, VideoInfo

#: Contracted tracks-dataframe columns (CONTRACTS.md section 7).
TRACK_COLUMNS: tuple[str, ...] = (
    "frame_index",
    "t_s",
    "track_id",
    "x1",
    "y1",
    "x2",
    "y2",
    "confidence",
)

#: Frame period of the synthetic handoff scenario, in seconds.
HANDOFF_DT_S = 0.1

#: Number of frames in the synthetic handoff scenario.
HANDOFF_FRAMES = 40


def handoff_video_info() -> VideoInfo:
    """Video metadata matching :func:`build_handoff_tracks_df`."""
    return VideoInfo(duration_s=4.0, fps=10.0, width=1000, height=600, frame_count=40)


def empty_tracks_df() -> pd.DataFrame:
    """An empty tracks dataframe with the contracted columns."""
    return pd.DataFrame(columns=list(TRACK_COLUMNS))


def build_handoff_tracks_df() -> pd.DataFrame:
    """Synthetic tracks producing at least one touch and one pass.

    Scenario (40 frames at 10 fps, 1000x600 px):

    - track 1 moves steadily for frames 0-19 then freezes; while it is the
      only mover, the motion centroid sits on it, so it possesses.
    - track 2 is frozen for frames 0-19 then moves for frames 20-39, taking
      over possession 0.1 s after track 1's run ends -> a pass handoff.
    - track 3 is static and far away (a third track keeps the team clustering
      in single-cluster mode, so the handoff is a pass, not a turnover).
    """
    rows: list[dict[str, float | int]] = []
    box_w, box_h = 20.0, 40.0

    def add(frame: int, track_id: int, cx: float, cy: float) -> None:
        rows.append(
            {
                "frame_index": frame,
                "t_s": round(frame * HANDOFF_DT_S, 3),
                "track_id": track_id,
                "x1": cx - box_w / 2.0,
                "y1": cy - box_h / 2.0,
                "x2": cx + box_w / 2.0,
                "y2": cy + box_h / 2.0,
                "confidence": 0.9,
            }
        )

    for frame in range(HANDOFF_FRAMES):
        add(frame, 1, 100.0 + 5.0 * min(frame, 19), 300.0)
        add(frame, 2, 800.0 + 5.0 * max(0, frame - 19), 300.0)
        add(frame, 3, 450.0, 100.0)
    return pd.DataFrame(rows)


def make_identity(
    track_id: int = 1,
    jersey_number: int | None = 9,
    player_id: str | None = "player-1",
    confidence: float = 0.8,
    method: str = "ocr",
) -> IdentityResult:
    """One estimated identity with overridable fields."""
    return IdentityResult(
        track_id=track_id,
        jersey_number=jersey_number,
        player_id=player_id,
        confidence=confidence,
        method=method,
    )


def make_stats_row(
    track_id: int = 1,
    player_id: str | None = "player-1",
    jersey_number: int | None = 9,
    minutes_tracked: float = 12.5,
    touches: int = 10,
) -> PlayerStatsRow:
    """One player stats row with sensible non-zero defaults."""
    return PlayerStatsRow(
        track_id=track_id,
        player_id=player_id,
        jersey_number=jersey_number,
        minutes_tracked=minutes_tracked,
        distance_proxy_m=850.0,
        touches=touches,
        passes=4,
        tackles=1,
        shots=2,
        turnovers=1,
        scoring_events=1,
        avg_confidence=0.83,
    )


def make_events() -> list[EventSpan]:
    """A small deterministic event list spanning three types."""
    return [
        EventSpan(event_type="touch", t_start_s=1.0, t_end_s=2.0, track_id=1, confidence=0.8),
        EventSpan(event_type="pass", t_start_s=2.0, t_end_s=2.5, track_id=1, confidence=0.7),
        EventSpan(
            event_type="shot_attempt", t_start_s=30.0, t_end_s=30.5, track_id=2, confidence=0.5
        ),
    ]
