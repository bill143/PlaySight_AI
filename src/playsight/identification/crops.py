"""Jersey-region crop sampling from tracked video frames."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pandas as pd

from playsight.core.logging import get_logger

#: Maximum crops sampled per track (K per CONTRACTS scope).
MAX_CROPS_PER_TRACK = 12

#: Fraction of box width trimmed from each side for the jersey region.
_X_INSET = 0.15
#: Jersey region vertical band inside the person box (below head, upper torso).
_Y_TOP = 0.18
_Y_BOTTOM = 0.55
#: Minimum crop dimension in pixels; smaller crops are useless for OCR/Re-ID.
_MIN_CROP_PX = 4


def jersey_crop(
    frame_bgr: np.ndarray, x1: float, y1: float, x2: float, y2: float
) -> np.ndarray | None:
    """Extract the upper-torso (jersey) region of a person box.

    The crop is the horizontal middle of the box between ~18% and ~55% of its
    height — below the head, over the chest, where jersey numbers sit.

    Args:
        frame_bgr: Full HxWx3 BGR frame.
        x1: Person box left edge (absolute pixels).
        y1: Person box top edge.
        x2: Person box right edge.
        y2: Person box bottom edge.

    Returns:
        The BGR crop, or None when the region is degenerate or too small.
    """
    frame_h, frame_w = int(frame_bgr.shape[0]), int(frame_bgr.shape[1])
    box_w = x2 - x1
    box_h = y2 - y1
    if box_w <= 2 or box_h <= 2:
        return None

    cx1 = int(max(0.0, min(x1 + _X_INSET * box_w, float(frame_w))))
    cx2 = int(max(0.0, min(x2 - _X_INSET * box_w, float(frame_w))))
    cy1 = int(max(0.0, min(y1 + _Y_TOP * box_h, float(frame_h))))
    cy2 = int(max(0.0, min(y1 + _Y_BOTTOM * box_h, float(frame_h))))
    if cx2 - cx1 < _MIN_CROP_PX or cy2 - cy1 < _MIN_CROP_PX:
        return None
    return frame_bgr[cy1:cy2, cx1:cx2].copy()


def sample_track_crops(
    video_path: str | Path,
    tracks_df: pd.DataFrame,
    max_crops_per_track: int = MAX_CROPS_PER_TRACK,
) -> dict[int, list[np.ndarray]]:
    """Sample up to K jersey crops per track from the source video.

    For each track, up to ``max_crops_per_track`` observations spread evenly
    across the track's lifetime are selected, the corresponding frames are
    decoded once each, and the jersey region of each box is cropped.

    Args:
        video_path: Local path of the source video.
        tracks_df: Tracks dataframe with columns
            ``frame_index, t_s, track_id, x1, y1, x2, y2, confidence``.
        max_crops_per_track: Cap on sampled crops per track.

    Returns:
        Mapping ``track_id -> list of BGR crops`` (tracks whose crops were all
        degenerate, and all tracks when the video is unreadable, are absent).
    """
    log = get_logger(__name__)
    crops: dict[int, list[np.ndarray]] = {}
    if tracks_df.empty:
        return crops

    # frame_index -> [(track_id, (x1, y1, x2, y2)), ...]
    wanted: dict[int, list[tuple[int, tuple[float, float, float, float]]]] = {}
    for track_id, group in tracks_df.groupby("track_id"):
        ordered = group.sort_values("frame_index")
        n = len(ordered)
        picks = np.unique(
            np.linspace(0, n - 1, num=min(max_crops_per_track, n)).round().astype(int)
        )
        for pick in picks:
            row = ordered.iloc[int(pick)]
            box = (float(row["x1"]), float(row["y1"]), float(row["x2"]), float(row["y2"]))
            wanted.setdefault(int(row["frame_index"]), []).append((int(track_id), box))

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        cap.release()
        log.warning("crop_sampling_video_unreadable", video_path=str(video_path))
        return crops
    try:
        for frame_index in sorted(wanted):
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
            ok, frame = cap.read()
            if not ok or frame is None:
                continue
            for track_id, box in wanted[frame_index]:
                crop = jersey_crop(frame, *box)
                if crop is not None:
                    crops.setdefault(track_id, []).append(crop)
    finally:
        cap.release()

    log.info(
        "track_crops_sampled",
        video_path=str(video_path),
        tracks=int(tracks_df["track_id"].nunique()),
        tracks_with_crops=len(crops),
        total_crops=sum(len(v) for v in crops.values()),
    )
    return crops
