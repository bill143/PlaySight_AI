"""Private helpers shared by the analytics modules for the tracks dataframe.

The tracks dataframe is the parquet artifact produced by the tracking stage
(CONTRACTS.md section 7): one row per (frame, track) with absolute-pixel
bounding boxes.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from playsight.core.types import VideoInfo

REQUIRED_TRACK_COLUMNS: tuple[str, ...] = (
    "frame_index",
    "t_s",
    "track_id",
    "x1",
    "y1",
    "x2",
    "y2",
    "confidence",
)

_FALLBACK_FRAME_DT_S = 0.04  # 25 fps equivalent, used when nothing better is known


def normalize_tracks(tracks_df: pd.DataFrame) -> pd.DataFrame | None:
    """Validate, coerce, and sort a tracks dataframe for analytics use.

    Returns a new dataframe with dtypes coerced to the contract, centroid
    columns ``cx``/``cy`` added, and rows sorted by ``(frame_index, track_id)``.
    Returns ``None`` when no usable rows remain (empty input, or every row
    dropped because of NaNs).

    Args:
        tracks_df: raw tracks dataframe (CONTRACTS.md section 7 columns).

    Raises:
        ValueError: if a required column is missing (a programming error, not
            a data-quality condition).
    """
    missing = [column for column in REQUIRED_TRACK_COLUMNS if column not in tracks_df.columns]
    if missing:
        raise ValueError(f"tracks_df is missing required columns: {missing}")
    if tracks_df.empty:
        return None
    df = tracks_df.loc[:, list(REQUIRED_TRACK_COLUMNS)].dropna()
    if df.empty:
        return None
    df = df.astype(
        {
            "frame_index": np.int64,
            "track_id": np.int64,
            "t_s": np.float64,
            "x1": np.float64,
            "y1": np.float64,
            "x2": np.float64,
            "y2": np.float64,
            "confidence": np.float64,
        }
    )
    df["cx"] = (df["x1"] + df["x2"]) / 2.0
    df["cy"] = (df["y1"] + df["y2"]) / 2.0
    return df.sort_values(["frame_index", "track_id"], kind="mergesort").reset_index(drop=True)


def frame_dims(df: pd.DataFrame, video_info: VideoInfo | None) -> tuple[float, float]:
    """Return the frame ``(width, height)`` in pixels.

    Prefers the probed video metadata; falls back to the maximum box extents
    observed in the tracks so downstream ratios stay finite.

    Args:
        df: normalized tracks dataframe (see :func:`normalize_tracks`).
        video_info: probed video metadata, if available.
    """
    width = float(video_info.width) if video_info is not None and video_info.width > 0 else 0.0
    height = float(video_info.height) if video_info is not None and video_info.height > 0 else 0.0
    if width <= 0.0:
        width = max(float(df["x2"].max()), 1.0)
    if height <= 0.0:
        height = max(float(df["y2"].max()), 1.0)
    return width, height


def estimate_frame_dt(df: pd.DataFrame, video_info: VideoInfo | None) -> float:
    """Estimate the period between consecutive *processed* frames, in seconds.

    Uses the median positive gap between distinct ``t_s`` values, which already
    reflects any frame stride applied upstream. Falls back to ``1 / fps``, then
    ``duration / frame_count``, then a 25 fps default.

    Args:
        df: normalized tracks dataframe (see :func:`normalize_tracks`).
        video_info: probed video metadata, if available.
    """
    t_values = np.sort(df["t_s"].unique())
    if t_values.size >= 2:
        diffs = np.diff(t_values)
        diffs = diffs[diffs > 1e-9]
        if diffs.size:
            return float(np.median(diffs))
    if video_info is not None:
        if video_info.fps > 0:
            return 1.0 / float(video_info.fps)
        if video_info.frame_count > 0 and video_info.duration_s > 0:
            return float(video_info.duration_s) / float(video_info.frame_count)
    return _FALLBACK_FRAME_DT_S
