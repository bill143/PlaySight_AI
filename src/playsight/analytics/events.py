"""Rule-based match event heuristics (CONTRACTS.md section 8).

The six MVP event types are derived purely from the tracked bounding boxes
(the ``player_tracks`` dataframe) with pandas/numpy -- there is no ball
detection and no learned model. Every heuristic is an honest *proxy*:

- ``touch``          sustained proximity of one track to the per-frame motion
                     centroid (a crude "where the action is" estimate).
- ``pass``           a touch handoff between two tracks within 2 seconds.
- ``tackle``         two-track convergence followed by bounding-box overlap.
- ``shot_attempt``   high-velocity displacement of the motion centroid toward
                     a field end zone.
- ``turnover``       a touch handoff across the two spatial team clusters.
- ``scoring_event``  a shot attempt followed by a track discontinuity inside
                     the goal region.

Outputs are deterministic for a given input dataframe. Confidence values are
heuristic scores in ``[0, 1]``, NOT calibrated probabilities, and the events
must never be presented as ground truth (refined in M5).
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import pairwise
from typing import Any

import numpy as np
import pandas as pd

from playsight.analytics._tracks import estimate_frame_dt, frame_dims, normalize_tracks
from playsight.config.settings import Settings
from playsight.core.logging import get_logger
from playsight.core.types import EventSpan, EventType, VideoInfo

__all__ = ["compute_events"]

# --- Heuristic tuning constants (documented proxies; revisited in M5) ---------------
_MIN_FRAMES = 5  # fewer distinct processed frames than this -> no events
_POSSESSION_RADIUS_FRAC = 0.12  # possession radius as a fraction of the frame diagonal
_POSSESSION_GAP_FRAMES = 2  # tolerated possession dropout (frames) inside one touch run
_TOUCH_MIN_S = 0.3  # minimum sustained possession duration for a touch
_PASS_MAX_GAP_S = 2.0  # max handoff gap between two touches (contract section 8)
_MIN_EVENT_SPAN_S = 0.05  # events always span a non-zero interval
_TEAM_MIN_TRACKS = 4  # below this, team clustering is meaningless -> one cluster
_TEAM_MIN_SPREAD_FRAC = 0.10  # min mean-x spread (fraction of width) to split clusters
_TACKLE_IOU_MIN = 0.10  # bbox overlap threshold for contact
_TACKLE_MIN_FRAMES = 2  # contact must persist for at least this many frames
_TACKLE_LOOKBACK_S = 0.5  # convergence evidence window before contact
_TACKLE_APPROACH_FRAC = 0.02  # centroids must close by this fraction of the diagonal
_TACKLE_MERGE_GAP_S = 1.0  # contact gaps below this merge into a single tackle
_TACKLE_PAIR_DIST_FRAC = 0.5  # ignore track pairs further apart than this (memory guard)
_SHOT_SPEED_FRAC = 0.35  # motion-centroid speed threshold, diagonal fractions per second
_SHOT_PROJECT_S = 0.5  # projection horizon to test "heading into the end zone"
_SHOT_GAP_S = 0.35  # hot-frame gaps below this merge into one shot window
_SHOT_ATTRIBUTION_S = 1.5  # how far back to look for the possessing track
_END_ZONE_FRAC = 0.18  # outer fraction of the frame width treated as field ends
_GOAL_ZONE_FRAC = 0.15  # outer fraction of the frame width treated as the goal region
_SCORING_LOOKAHEAD_S = 3.0  # window after a shot to look for a track discontinuity


@dataclass
class _Run:
    """One sustained possession run by a single track (a touch candidate)."""

    track_id: int
    t0: float
    t1: float
    n: int
    dist_sum: float


def compute_events(
    tracks_df: pd.DataFrame,
    video_info: VideoInfo,
    settings: Settings | None = None,
) -> list[EventSpan]:
    """Segment the six rule-based event types from tracked bounding boxes.

    Implements the CONTRACTS.md section 8 heuristics with pure pandas/numpy.
    Deterministic for a given input; every event carries a heuristic
    ``confidence`` in ``[0, 1]`` and a ``[t_start_s, t_end_s]`` span.

    Args:
        tracks_df: tracks dataframe with columns ``frame_index, t_s, track_id,
            x1, y1, x2, y2, confidence`` (CONTRACTS.md section 7).
        video_info: probed video metadata (frame dimensions scale thresholds).
        settings: application settings; reserved for future threshold tuning
            (the current heuristics use the documented module constants).

    Returns:
        Events sorted by start time. Empty list for empty or too-short inputs
        (fewer than 5 distinct frames or zero elapsed time).
    """
    log = get_logger(__name__)
    df = normalize_tracks(tracks_df)
    if df is None:
        return []
    distinct_frames = int(df["frame_index"].nunique())
    duration_s = float(df["t_s"].max() - df["t_s"].min())
    if distinct_frames < _MIN_FRAMES or duration_s <= 0.0:
        log.info("compute_events_input_too_short", frames=distinct_frames, duration_s=duration_s)
        return []

    width, height = frame_dims(df, video_info)
    diag = float(np.hypot(width, height))
    frames = _motion_centroids(df)
    possession = _assign_possession(df, frames, diag)
    runs = _possession_runs(possession)
    team_of = _team_clusters(df, width)
    frame_dt = estimate_frame_dt(df, video_info)

    events: list[EventSpan] = []
    events.extend(_touch_events(runs, diag))
    events.extend(_handoff_events(runs, team_of))
    events.extend(_tackle_events(df, runs, diag))
    shots = _shot_events(frames, runs, width, diag)
    events.extend(shots)
    events.extend(_scoring_events(shots, df, width, frame_dt, float(df["t_s"].max())))
    events.sort(key=_event_sort_key)
    log.info(
        "compute_events_done",
        events=len(events),
        tracks=int(df["track_id"].nunique()),
        frames=distinct_frames,
        duration_s=round(duration_s, 3),
    )
    return events


def _event_sort_key(event: EventSpan) -> tuple[float, str, int]:
    """Deterministic ordering: start time, then type, then track."""
    return (event.t_start_s, event.event_type, -1 if event.track_id is None else event.track_id)


def _clip(value: float, lo: float, hi: float) -> float:
    """Clamp ``value`` into ``[lo, hi]``."""
    return max(lo, min(hi, value))


def _motion_centroids(df: pd.DataFrame) -> pd.DataFrame:
    """Per-frame motion centroid: track centroids weighted by instantaneous speed.

    The motion centroid is a crude "where is the action" proxy standing in for
    ball position (there is no ball detection in the MVP). Frames where nothing
    moves degrade to the plain mean of all centroids.

    Returns:
        Frame table with columns ``frame_index, t_s, mx, my, vx, vy, v``
        sorted by frame index.
    """
    work = df[["frame_index", "t_s", "track_id", "cx", "cy"]].copy()
    grouped = work.groupby("track_id")
    dt = grouped["t_s"].diff()
    step = np.hypot(grouped["cx"].diff(), grouped["cy"].diff())
    work["speed"] = (step / dt.where(dt > 1e-9)).fillna(0.0)
    work["weight"] = work["speed"] + 1e-6
    work["wx"] = work["cx"] * work["weight"]
    work["wy"] = work["cy"] * work["weight"]
    per_frame = work.groupby("frame_index", sort=True)
    frames = pd.DataFrame(
        {
            "t_s": per_frame["t_s"].first(),
            "mx": per_frame["wx"].sum() / per_frame["weight"].sum(),
            "my": per_frame["wy"].sum() / per_frame["weight"].sum(),
        }
    ).reset_index()
    frame_dt = frames["t_s"].diff()
    frames["vx"] = (frames["mx"].diff() / frame_dt).where(frame_dt > 1e-9, 0.0)
    frames["vy"] = (frames["my"].diff() / frame_dt).where(frame_dt > 1e-9, 0.0)
    frames["v"] = np.hypot(frames["vx"], frames["vy"])
    return frames


def _assign_possession(df: pd.DataFrame, frames: pd.DataFrame, diag: float) -> pd.DataFrame:
    """Per frame, pick the possessing track: nearest to the motion centroid.

    Frames where even the nearest track is outside the possession radius get
    ``track_id == -1`` (nobody possesses).

    Returns:
        One row per frame with columns ``frame_index, t_s, track_id, dist``.
    """
    merged = df[["frame_index", "t_s", "track_id", "cx", "cy"]].merge(
        frames[["frame_index", "mx", "my"]], on="frame_index", how="left"
    )
    merged["dist"] = np.hypot(merged["cx"] - merged["mx"], merged["cy"] - merged["my"])
    best_idx = merged.groupby("frame_index")["dist"].idxmin()
    best = merged.loc[best_idx, ["frame_index", "t_s", "track_id", "dist"]]
    radius = _POSSESSION_RADIUS_FRAC * diag
    best["track_id"] = best["track_id"].where(best["dist"] <= radius, -1)
    return best.sort_values("frame_index").reset_index(drop=True)


def _possession_runs(possession: pd.DataFrame) -> list[_Run]:
    """Merge per-frame possession into sustained runs (touch candidates).

    Short dropouts (up to ``_POSSESSION_GAP_FRAMES`` unpossessed frames) are
    bridged; a switch to a different track always closes the current run. Only
    runs with at least two frames and ``_TOUCH_MIN_S`` duration qualify.
    """
    runs: list[_Run] = []
    current: _Run | None = None
    gap = 0
    for row in possession.itertuples(index=False):
        tid = int(row.track_id)
        if tid < 0:
            if current is not None:
                gap += 1
                if gap > _POSSESSION_GAP_FRAMES:
                    runs.append(current)
                    current = None
                    gap = 0
            continue
        if current is not None and tid == current.track_id:
            current.t1 = float(row.t_s)
            current.n += 1
            current.dist_sum += float(row.dist)
        else:
            if current is not None:
                runs.append(current)
            current = _Run(tid, float(row.t_s), float(row.t_s), 1, float(row.dist))
        gap = 0
    if current is not None:
        runs.append(current)
    return [run for run in runs if run.n >= 2 and (run.t1 - run.t0) >= _TOUCH_MIN_S]


def _possessor_at(runs: list[_Run], t: float, tolerance_s: float = 0.75) -> int | None:
    """Return the track possessing at time ``t``.

    Falls back to the run that ended most recently before ``t`` within
    ``tolerance_s``; returns ``None`` when there is no evidence.
    """
    best_track: int | None = None
    best_gap = tolerance_s
    for run in runs:
        if run.t0 <= t <= run.t1:
            return run.track_id
        gap = t - run.t1
        if 0.0 <= gap < best_gap:
            best_gap = gap
            best_track = run.track_id
    return best_track


def _touch_events(runs: list[_Run], diag: float) -> list[EventSpan]:
    """Touches: qualifying possession runs, scored by proximity and duration."""
    radius = _POSSESSION_RADIUS_FRAC * diag
    events: list[EventSpan] = []
    for run in runs:
        mean_dist = run.dist_sum / run.n
        proximity = 1.0 - min(1.0, mean_dist / radius)
        duration_bonus = min(0.15, (run.t1 - run.t0) / 20.0)
        confidence = _clip(0.35 + 0.45 * proximity + duration_bonus, 0.2, 0.95)
        events.append(
            EventSpan(
                event_type=EventType.TOUCH.value,
                t_start_s=round(run.t0, 3),
                t_end_s=round(max(run.t1, run.t0 + _MIN_EVENT_SPAN_S), 3),
                track_id=run.track_id,
                confidence=round(confidence, 3),
                meta={"n_frames": run.n, "mean_dist_px": round(mean_dist, 1)},
            )
        )
    return events


def _team_clusters(df: pd.DataFrame, width: float) -> dict[int, int]:
    """Assign each track to one of two spatial clusters (a crude team proxy).

    Deterministic 1-D 2-means over each track's mean centroid x. When there are
    too few tracks, or the spread is too small for a meaningful split, every
    track lands in cluster 0 (so no turnovers are produced).
    """
    mean_cx = df.groupby("track_id")["cx"].mean()
    track_ids = [int(track_id) for track_id in mean_cx.index]
    xs = mean_cx.to_numpy(dtype=np.float64)
    spread = float(xs.max() - xs.min()) if xs.size else 0.0
    if len(track_ids) < _TEAM_MIN_TRACKS or spread < _TEAM_MIN_SPREAD_FRAC * width:
        return {track_id: 0 for track_id in track_ids}
    centers = np.array([xs.min(), xs.max()], dtype=np.float64)
    assign = np.zeros(len(xs), dtype=np.int64)
    for _ in range(20):
        assign = (np.abs(xs - centers[0]) > np.abs(xs - centers[1])).astype(np.int64)
        for k in (0, 1):
            members = xs[assign == k]
            if members.size:
                centers[k] = members.mean()
    return {track_id: int(a) for track_id, a in zip(track_ids, assign, strict=True)}


def _handoff_events(runs: list[_Run], team_of: dict[int, int]) -> list[EventSpan]:
    """Passes and turnovers: touch handoffs between tracks within 2 seconds.

    A handoff inside the same team cluster is a ``pass``; across clusters it is
    a ``turnover``. Both are attributed to the track losing possession.
    """
    events: list[EventSpan] = []
    for prev, nxt in pairwise(runs):
        if prev.track_id == nxt.track_id:
            continue
        gap = nxt.t0 - prev.t1
        if gap < 0.0 or gap >= _PASS_MAX_GAP_S:
            continue
        from_team = team_of.get(prev.track_id, 0)
        to_team = team_of.get(nxt.track_id, 0)
        t_start = round(prev.t1, 3)
        t_end = round(max(nxt.t0, prev.t1 + _MIN_EVENT_SPAN_S), 3)
        confidence = _clip(0.7 - 0.15 * gap, 0.2, 0.9)
        meta: dict[str, Any] = {
            "from_track": prev.track_id,
            "to_track": nxt.track_id,
            "gap_s": round(gap, 3),
        }
        if from_team == to_team:
            events.append(
                EventSpan(
                    event_type=EventType.PASS.value,
                    t_start_s=t_start,
                    t_end_s=t_end,
                    track_id=prev.track_id,
                    confidence=round(confidence, 3),
                    meta=meta,
                )
            )
        else:
            meta["from_team"] = from_team
            meta["to_team"] = to_team
            events.append(
                EventSpan(
                    event_type=EventType.TURNOVER.value,
                    t_start_s=t_start,
                    t_end_s=t_end,
                    track_id=prev.track_id,
                    confidence=round(confidence * 0.9, 3),
                    meta=meta,
                )
            )
    return events


def _pairwise_iou(pairs: pd.DataFrame) -> np.ndarray:
    """Vectorized IoU for the ``_a`` / ``_b`` box columns of a pair table."""
    ix1 = np.maximum(pairs["x1_a"], pairs["x1_b"])
    iy1 = np.maximum(pairs["y1_a"], pairs["y1_b"])
    ix2 = np.minimum(pairs["x2_a"], pairs["x2_b"])
    iy2 = np.minimum(pairs["y2_a"], pairs["y2_b"])
    inter = np.clip(ix2 - ix1, 0.0, None) * np.clip(iy2 - iy1, 0.0, None)
    area_a = np.clip(pairs["x2_a"] - pairs["x1_a"], 0.0, None) * np.clip(
        pairs["y2_a"] - pairs["y1_a"], 0.0, None
    )
    area_b = np.clip(pairs["x2_b"] - pairs["x1_b"], 0.0, None) * np.clip(
        pairs["y2_b"] - pairs["y1_b"], 0.0, None
    )
    union = area_a + area_b - inter
    return np.where(union > 1e-9, inter / union, 0.0)


def _tackle_events(df: pd.DataFrame, runs: list[_Run], diag: float) -> list[EventSpan]:
    """Tackles: two tracks converge, then their boxes overlap for >= 2 frames.

    Attribution: the member of the pair that was NOT possessing just before
    contact is the tackler; without possession evidence, the lower track id.
    """
    columns = ["frame_index", "t_s", "track_id", "x1", "y1", "x2", "y2", "cx", "cy"]
    single = df[columns]
    pairs = single.merge(single, on="frame_index", suffixes=("_a", "_b"))
    pairs = pairs[pairs["track_id_a"] < pairs["track_id_b"]]
    if pairs.empty:
        return []
    pairs = pairs.copy()
    pairs["dist"] = np.hypot(pairs["cx_a"] - pairs["cx_b"], pairs["cy_a"] - pairs["cy_b"])
    pairs = pairs[pairs["dist"] <= _TACKLE_PAIR_DIST_FRAC * diag]
    if pairs.empty:
        return []
    pairs = pairs.copy()
    pairs["iou"] = _pairwise_iou(pairs)

    approach_px = _TACKLE_APPROACH_FRAC * diag
    events: list[EventSpan] = []
    for (track_a, track_b), group in pairs.groupby(["track_id_a", "track_id_b"], sort=True):
        group = group.sort_values("t_s_a")
        contact = group[group["iou"] >= _TACKLE_IOU_MIN]
        if len(contact) < _TACKLE_MIN_FRAMES:
            continue
        times = contact["t_s_a"].to_numpy(dtype=np.float64)
        breaks = np.where(np.diff(times) > _TACKLE_MERGE_GAP_S)[0]
        starts = np.concatenate(([0], breaks + 1))
        ends = np.concatenate((breaks, [len(times) - 1]))
        for seg_start, seg_end in zip(starts, ends, strict=True):
            if seg_end - seg_start + 1 < _TACKLE_MIN_FRAMES:
                continue
            seg = contact.iloc[int(seg_start) : int(seg_end) + 1]
            t0 = float(seg["t_s_a"].iloc[0])
            t1 = float(seg["t_s_a"].iloc[-1])
            before = group[(group["t_s_a"] >= t0 - _TACKLE_LOOKBACK_S) & (group["t_s_a"] < t0)]
            if before.empty:
                continue
            closing = float(before["dist"].max()) - float(seg["dist"].iloc[0])
            if closing < approach_px:
                continue
            peak_iou = float(seg["iou"].max())
            possessor = _possessor_at(runs, t0)
            pair_ids = (int(track_a), int(track_b))
            tackler = pair_ids[1] if possessor == pair_ids[0] else pair_ids[0]
            closing_bonus = 0.1 * min(1.0, closing / (4.0 * approach_px))
            confidence = _clip(0.3 + 0.8 * peak_iou + closing_bonus, 0.25, 0.9)
            events.append(
                EventSpan(
                    event_type=EventType.TACKLE.value,
                    t_start_s=round(t0, 3),
                    t_end_s=round(max(t1, t0 + _MIN_EVENT_SPAN_S), 3),
                    track_id=tackler,
                    confidence=round(confidence, 3),
                    meta={
                        "tracks": [pair_ids[0], pair_ids[1]],
                        "possessor_track": possessor,
                        "peak_iou": round(peak_iou, 3),
                        "closing_px": round(closing, 1),
                    },
                )
            )
    return events


def _shot_events(
    frames: pd.DataFrame, runs: list[_Run], width: float, diag: float
) -> list[EventSpan]:
    """Shot attempts: the motion centroid accelerates toward a field end zone.

    Attribution: the track possessing at (or just before) the window start.
    """
    if len(frames) < 3:
        return []
    speed_min = _SHOT_SPEED_FRAC * diag
    left_x = _END_ZONE_FRAC * width
    right_x = (1.0 - _END_ZONE_FRAC) * width
    projected_x = frames["mx"] + frames["vx"] * _SHOT_PROJECT_S
    toward_left = (frames["vx"] < 0.0) & (projected_x <= left_x)
    toward_right = (frames["vx"] > 0.0) & (projected_x >= right_x)
    hot = frames[(frames["v"] >= speed_min) & (toward_left | toward_right)]
    if len(hot) < 2:
        return []
    times = hot["t_s"].to_numpy(dtype=np.float64)
    breaks = np.where(np.diff(times) > _SHOT_GAP_S)[0]
    starts = np.concatenate(([0], breaks + 1))
    ends = np.concatenate((breaks, [len(times) - 1]))
    events: list[EventSpan] = []
    for seg_start, seg_end in zip(starts, ends, strict=True):
        if seg_end - seg_start + 1 < 2:
            continue
        seg = hot.iloc[int(seg_start) : int(seg_end) + 1]
        t0 = float(seg["t_s"].iloc[0])
        t1 = float(seg["t_s"].iloc[-1])
        direction = "left" if int((seg["vx"] < 0.0).sum()) * 2 >= len(seg) else "right"
        track_id = _possessor_at(runs, t0, tolerance_s=_SHOT_ATTRIBUTION_S)
        peak_speed = float(seg["v"].max())
        attribution_bonus = 0.1 if track_id is not None else 0.0
        speed_bonus = 0.3 * min(1.0, peak_speed / (2.0 * speed_min))
        confidence = _clip(0.3 + speed_bonus + attribution_bonus, 0.25, 0.85)
        events.append(
            EventSpan(
                event_type=EventType.SHOT_ATTEMPT.value,
                t_start_s=round(t0, 3),
                t_end_s=round(max(t1, t0 + _MIN_EVENT_SPAN_S), 3),
                track_id=track_id,
                confidence=round(confidence, 3),
                meta={"direction": direction, "peak_speed_px_s": round(peak_speed, 1)},
            )
        )
    return events


def _scoring_events(
    shots: list[EventSpan],
    df: pd.DataFrame,
    width: float,
    frame_dt: float,
    video_end_s: float,
) -> list[EventSpan]:
    """Scoring events: a shot followed by a track ending inside the goal region.

    Tracks whose last observation coincides with the end of the video are
    excluded (they end because the video ends, not because of a goal reset).
    """
    if not shots:
        return []
    last_rows = df.groupby("track_id", sort=True).tail(1)
    goal_left = _GOAL_ZONE_FRAC * width
    goal_right = (1.0 - _GOAL_ZONE_FRAC) * width
    truncation_cutoff = video_end_s - 2.0 * frame_dt
    events: list[EventSpan] = []
    for shot in shots:
        direction = str(shot.meta.get("direction", ""))
        for row in last_rows.itertuples(index=False):
            last_t = float(row.t_s)
            if last_t >= truncation_cutoff:
                continue
            if not shot.t_end_s < last_t <= shot.t_end_s + _SCORING_LOOKAHEAD_S:
                continue
            cx = float(row.cx)
            in_goal = (direction == "left" and cx <= goal_left) or (
                direction == "right" and cx >= goal_right
            )
            if not in_goal:
                continue
            events.append(
                EventSpan(
                    event_type=EventType.SCORING_EVENT.value,
                    t_start_s=shot.t_start_s,
                    t_end_s=round(last_t, 3),
                    track_id=shot.track_id,
                    confidence=round(_clip(shot.confidence * 0.75, 0.2, 0.55), 3),
                    meta={
                        "shot_direction": direction,
                        "discontinued_track": int(row.track_id),
                        "shot_confidence": shot.confidence,
                    },
                )
            )
            break  # at most one scoring event per shot
    return events
