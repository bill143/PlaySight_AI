"""Annotated match video export (CONTRACTS.md section 7).

Reads the source video with OpenCV, draws per-track bounding boxes with track
id + jersey labels and a minimal HUD (match clock), and writes an MP4.

The vision pipeline only processes every ``settings.pipeline.frame_stride``-th
frame, so this renderer annotates exactly those frames and duplicates each
annotated frame across the strided gap — output frame count and duration match
the source. The intermediate file is written with OpenCV's ``mp4v`` codec and
then re-encoded to H.264 via ffmpeg (when available) for browser playback.
"""

from __future__ import annotations

import colorsys
import os
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import pandas as pd

from playsight.config.settings import Settings, get_settings
from playsight.core.errors import ExternalServiceError, ValidationFailed
from playsight.core.logging import get_logger
from playsight.core.types import IdentityResult
from playsight.highlights.ffmpeg_util import ffmpeg_available, run_ffmpeg

_FONT = cv2.FONT_HERSHEY_SIMPLEX

#: (track_id, x1, y1, x2, y2) in absolute pixel coordinates.
_Box = tuple[int, int, int, int, int]

_REQUIRED_COLUMNS = frozenset({"frame_index", "track_id", "x1", "y1", "x2", "y2"})


def render_annotated_video(
    video_path: str | Path,
    tracks_df: pd.DataFrame,
    identities: Sequence[IdentityResult],
    out_path: str | Path,
    *,
    settings: Settings | None = None,
) -> Path:
    """Render an annotated copy of a match video with boxes, labels and a clock.

    Args:
        video_path: Source match video.
        tracks_df: Tracks dataframe with at least ``frame_index``, ``track_id``,
            ``x1``, ``y1``, ``x2``, ``y2`` columns (CONTRACTS.md section 7).
        identities: Identity results used to label tracks with jersey numbers.
        out_path: Destination MP4 path (``annotated_video.mp4`` per section 9).
        settings: Optional settings override (defaults to the process settings);
            ``settings.pipeline.frame_stride`` controls which frames are
            annotated (skipped frames repeat the previous annotated frame so
            duration is preserved) and ``settings.pipeline.max_frames`` caps
            the number of annotated frames for smoke runs.

    Returns:
        The path to the written video (== ``out_path``).

    Raises:
        ValidationFailed: If the video is missing/unreadable or the tracks
            dataframe lacks required columns.
        ExternalServiceError: If the OpenCV writer cannot be opened.
    """
    log = get_logger(__name__)
    cfg = settings if settings is not None else get_settings()
    stride = max(1, int(cfg.pipeline.frame_stride))
    max_frames = cfg.pipeline.max_frames

    video = Path(video_path)
    out = Path(out_path)
    if not video.is_file():
        raise ValidationFailed(f"video file not found: {video}")

    boxes = _boxes_by_frame(tracks_df)
    labels = {identity.track_id: _identity_label(identity) for identity in identities}
    out.parent.mkdir(parents=True, exist_ok=True)
    raw = out.with_name(out.stem + ".raw.mp4")

    log.info(
        "annotate_render_started",
        video=str(video),
        out=str(out),
        stride=stride,
        tracks=len({b[0] for frame_boxes in boxes.values() for b in frame_boxes}),
    )
    try:
        written, annotated_count = _render_raw(video, raw, boxes, labels, stride, max_frames, log)
    except Exception:
        raw.unlink(missing_ok=True)
        raise
    if written == 0:
        raw.unlink(missing_ok=True)
        raise ValidationFailed(f"no frames decoded from video: {video}")

    _finalize_mp4(raw, out, log)
    log.info(
        "annotate_render_finished",
        out=str(out),
        frames_written=written,
        frames_annotated=annotated_count,
    )
    return out


def _identity_label(identity: IdentityResult) -> str:
    """Return the on-video label for a track: ``T<track_id>`` plus jersey number."""
    label = f"T{identity.track_id}"
    if identity.jersey_number is not None:
        label += f" #{identity.jersey_number}"
    return label


def _track_color(track_id: int) -> tuple[int, int, int]:
    """Return a deterministic, well-separated BGR color for a track id."""
    hue = (track_id * 0.61803398875) % 1.0  # golden-ratio hue spacing
    red, green, blue = colorsys.hsv_to_rgb(hue, 0.85, 0.95)
    return int(blue * 255), int(green * 255), int(red * 255)


def _format_clock(t_s: float) -> str:
    """Format seconds as a ``MM:SS`` match clock string."""
    total = max(0, int(t_s))
    return f"{total // 60:02d}:{total % 60:02d}"


def _boxes_by_frame(tracks_df: pd.DataFrame) -> dict[int, list[_Box]]:
    """Index the tracks dataframe as ``frame_index -> [(track_id, x1, y1, x2, y2)]``."""
    boxes: dict[int, list[_Box]] = {}
    if tracks_df is None or tracks_df.empty:
        return boxes
    missing = _REQUIRED_COLUMNS - set(tracks_df.columns)
    if missing:
        raise ValidationFailed(f"tracks dataframe is missing columns: {sorted(missing)}")
    for row in tracks_df.itertuples(index=False):
        boxes.setdefault(int(row.frame_index), []).append(
            (int(row.track_id), int(row.x1), int(row.y1), int(row.x2), int(row.y2))
        )
    return boxes


def _clip(value: int, upper: int) -> int:
    """Clamp a pixel coordinate to ``[0, upper - 1]``."""
    return max(0, min(value, upper - 1))


def _draw_frame(
    frame: np.ndarray,
    frame_boxes: list[_Box],
    labels: dict[int, str],
    t_s: float,
) -> None:
    """Draw track boxes, labels and the match-clock HUD onto ``frame`` in place."""
    height, width = frame.shape[:2]
    for track_id, x1, y1, x2, y2 in frame_boxes:
        color = _track_color(track_id)
        p1 = (_clip(x1, width), _clip(y1, height))
        p2 = (_clip(x2, width), _clip(y2, height))
        cv2.rectangle(frame, p1, p2, color, 2)
        label = labels.get(track_id, f"T{track_id}")
        (text_w, text_h), baseline = cv2.getTextSize(label, _FONT, 0.5, 1)
        text_y = p1[1] - 6 if p1[1] - text_h - 8 >= 0 else min(height - 2, p1[1] + text_h + 8)
        cv2.rectangle(
            frame,
            (p1[0], text_y - text_h - 4),
            (min(width - 1, p1[0] + text_w + 6), text_y + baseline),
            color,
            -1,
        )
        cv2.putText(frame, label, (p1[0] + 3, text_y), _FONT, 0.5, (0, 0, 0), 1, cv2.LINE_AA)
    # Minimal HUD: match clock, top-left.
    cv2.rectangle(frame, (8, 8), (116, 42), (16, 16, 16), -1)
    cv2.putText(frame, _format_clock(t_s), (18, 34), _FONT, 0.7, (255, 255, 255), 2, cv2.LINE_AA)


def _render_raw(
    video: Path,
    raw: Path,
    boxes: dict[int, list[_Box]],
    labels: dict[int, str],
    stride: int,
    max_frames: int | None,
    log: Any,
) -> tuple[int, int]:
    """Decode ``video``, annotate every ``stride``-th frame and write ``raw``.

    Skipped frames are only grabbed (not decoded) and the last annotated frame
    is written in their place, preserving frame count and duration.

    Returns:
        ``(frames_written, frames_annotated)``.
    """
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise ValidationFailed(f"could not open video for reading: {video}")
    writer = None
    try:
        fps = float(cap.get(cv2.CAP_PROP_FPS))
        if fps <= 0:
            fps = 25.0
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        if width <= 0 or height <= 0:
            raise ValidationFailed(f"video reports invalid dimensions {width}x{height}: {video}")
        writer = cv2.VideoWriter(str(raw), cv2.VideoWriter.fourcc(*"mp4v"), fps, (width, height))
        if not writer.isOpened():
            raise ExternalServiceError(
                f"could not open OpenCV mp4 writer at {raw}", code="video_writer_failed"
            )
        frame_index = 0
        annotated_count = 0
        written = 0
        current: Any = None
        while cap.grab():
            if frame_index % stride == 0:
                if max_frames is not None and annotated_count >= max_frames:
                    log.info("annotate_frame_cap_reached", max_frames=max_frames)
                    break
                ok, frame = cap.retrieve()
                if not ok:
                    break
                _draw_frame(frame, boxes.get(frame_index, []), labels, frame_index / fps)
                current = frame
                annotated_count += 1
            if current is not None:
                writer.write(current)
                written += 1
            frame_index += 1
        return written, annotated_count
    finally:
        if writer is not None:
            writer.release()
        cap.release()


def _finalize_mp4(raw: Path, out: Path, log: Any) -> None:
    """Re-encode the mp4v intermediate to H.264 for browser playback.

    When ffmpeg is unavailable (or the re-encode fails), the mp4v file is kept
    as the final artifact rather than failing the export.
    """
    if ffmpeg_available():
        args = [
            "-i",
            str(raw),
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "23",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            "-an",
            str(out),
        ]
        try:
            run_ffmpeg(args, log)
        except ExternalServiceError as exc:
            log.warning("annotate_h264_reencode_failed", error=exc.message)
        else:
            raw.unlink(missing_ok=True)
            return
    os.replace(raw, out)
    log.info("annotate_kept_mp4v_output", out=str(out))
