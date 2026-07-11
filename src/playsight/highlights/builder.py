"""Per-player highlight reel building (CONTRACTS.md sections 7 and 9).

Given the event spans detected for a match and a resolved (or unresolved)
identity, this module cuts padded clips around the identity's events with
ffmpeg and concatenates them into a single MP4 highlight reel.

Cutting strategy: stream-copy first (fast, no quality loss); if that fails or
produces an empty file (e.g. exotic codecs, no clean keyframes), fall back to
re-encoding with libx264/aac. Concatenation uses the ffmpeg concat demuxer
with a temporary file list.
"""

from __future__ import annotations

import tempfile
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

from playsight.core.errors import ExternalServiceError, ValidationFailed
from playsight.core.logging import get_logger
from playsight.core.types import EventSpan, IdentityResult
from playsight.highlights.ffmpeg_util import run_ffmpeg

#: Minimum duration of a single cut clip in seconds (guards degenerate spans).
_MIN_CLIP_S = 0.5

#: Re-encode arguments used for both the per-clip and concat fallbacks.
_ENCODE_ARGS: tuple[str, ...] = (
    "-c:v",
    "libx264",
    "-preset",
    "veryfast",
    "-crf",
    "23",
    "-c:a",
    "aac",
    "-movflags",
    "+faststart",
)


def merge_time_windows(windows: Iterable[tuple[float, float]]) -> list[tuple[float, float]]:
    """Merge overlapping or touching ``(t0, t1)`` windows into a sorted list.

    Args:
        windows: Arbitrary-order time windows; each is normalized so t0 <= t1.

    Returns:
        Non-overlapping windows sorted by start time.
    """
    ordered = sorted((min(a, b), max(a, b)) for a, b in windows)
    merged: list[tuple[float, float]] = []
    for t0, t1 in ordered:
        if merged and t0 <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], t1))
        else:
            merged.append((t0, t1))
    return merged


def select_event_windows(
    events: Iterable[EventSpan],
    track_id: int,
    padding_s: float = 1.5,
) -> list[tuple[float, float]]:
    """Return merged clip windows for all events belonging to ``track_id``.

    Each event span is padded by ``padding_s`` on both sides (clamped at 0),
    widened to at least ``_MIN_CLIP_S`` seconds, then overlapping windows are
    merged so the reel never repeats footage.

    Args:
        events: All event spans detected for the match.
        track_id: The track whose events should be selected.
        padding_s: Context padding added before/after each event, in seconds.

    Returns:
        Merged ``(t0, t1)`` windows sorted by start time (may be empty).
    """
    padding = max(0.0, padding_s)
    windows: list[tuple[float, float]] = []
    for event in events:
        if event.track_id != track_id:
            continue
        start = min(event.t_start_s, event.t_end_s)
        end = max(event.t_start_s, event.t_end_s)
        t0 = max(0.0, start - padding)
        t1 = end + padding
        if t1 - t0 < _MIN_CLIP_S:
            t1 = t0 + _MIN_CLIP_S
        windows.append((t0, t1))
    return merge_time_windows(windows)


def build_player_highlights(
    video_path: str | Path,
    events: Sequence[EventSpan],
    identity: IdentityResult,
    out_path: str | Path,
    padding_s: float = 1.5,
) -> Path:
    """Build a per-player highlight reel MP4 from a match video.

    Selects the events attributed to ``identity.track_id``, pads and merges
    their time windows, cuts each window with ffmpeg (stream-copy with a
    re-encode fallback) and concatenates the clips via the concat demuxer.

    Args:
        video_path: Source match video.
        events: All event spans detected for the match.
        identity: Identity whose track's events form the reel.
        out_path: Destination MP4 path
            (``player_highlights_<player_id>.mp4`` per CONTRACTS.md section 9).
        padding_s: Context padding around each event in seconds.

    Returns:
        The path to the written highlight reel (== ``out_path``).

    Raises:
        ValidationFailed: If the source video is missing or no events exist
            for the identity's track (nothing to build a reel from).
        ExternalServiceError: If ffmpeg is unavailable or fails.
    """
    log = get_logger(__name__)
    video = Path(video_path)
    out = Path(out_path)
    if not video.is_file():
        raise ValidationFailed(f"video file not found: {video}")

    windows = select_event_windows(events, identity.track_id, padding_s=padding_s)
    if not windows:
        raise ValidationFailed(
            f"no events found for track_id={identity.track_id} "
            f"(jersey={identity.jersey_number}, player_id={identity.player_id}); "
            "cannot build a highlight reel from zero events"
        )

    out.parent.mkdir(parents=True, exist_ok=True)
    log.info(
        "highlights_build_started",
        video=str(video),
        out=str(out),
        track_id=identity.track_id,
        clip_count=len(windows),
    )

    with tempfile.TemporaryDirectory(prefix="playsight_highlights_") as tmp:
        tmp_dir = Path(tmp)
        clip_paths: list[Path] = []
        for index, (t0, t1) in enumerate(windows):
            clip_path = tmp_dir / f"clip_{index:04d}.mp4"
            _cut_clip(video, t0, t1, clip_path, log)
            clip_paths.append(clip_path)
        _concat_clips(clip_paths, out, tmp_dir, log)

    if not out.is_file() or out.stat().st_size == 0:
        raise ExternalServiceError(
            f"ffmpeg produced no highlight output at {out}", code="ffmpeg_failed"
        )
    log.info("highlights_build_finished", out=str(out), clip_count=len(windows))
    return out


def _cut_clip(video: Path, t0: float, t1: float, clip_path: Path, log: Any) -> None:
    """Cut ``[t0, t1]`` from ``video`` into ``clip_path``.

    Tries a fast stream copy first; on failure (or empty output) re-encodes
    with libx264/aac for maximum compatibility.
    """
    duration = t1 - t0
    base = ["-ss", f"{t0:.3f}", "-i", str(video), "-t", f"{duration:.3f}"]
    copy_args = [*base, "-c", "copy", "-avoid_negative_ts", "make_zero", str(clip_path)]
    try:
        run_ffmpeg(copy_args, log)
    except ExternalServiceError as exc:
        if exc.code == "ffmpeg_not_found":
            raise
        log.warning("highlights_stream_copy_failed", t0=t0, t1=t1, error=exc.message)
    else:
        if clip_path.is_file() and clip_path.stat().st_size > 0:
            return
        log.warning("highlights_stream_copy_empty", t0=t0, t1=t1)
    encode_args = [*base, *_ENCODE_ARGS, str(clip_path)]
    run_ffmpeg(encode_args, log)
    if not clip_path.is_file() or clip_path.stat().st_size == 0:
        raise ExternalServiceError(
            f"ffmpeg failed to cut clip [{t0:.3f}s, {t1:.3f}s] from {video}",
            code="ffmpeg_failed",
        )


def _concat_clips(clip_paths: Sequence[Path], out: Path, tmp_dir: Path, log: Any) -> None:
    """Concatenate clips into ``out`` via the ffmpeg concat demuxer.

    Writes a temporary file list, tries a stream-copy concat first, and falls
    back to a re-encode concat when the copy fails or writes nothing.
    """
    list_path = tmp_dir / "filelist.txt"
    lines = []
    for clip in clip_paths:
        # Concat-demuxer quoting: single-quoted path; embedded quotes use '\''.
        quoted = clip.resolve().as_posix().replace("'", "'\\''")
        lines.append(f"file '{quoted}'")
    list_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    base = ["-f", "concat", "-safe", "0", "-i", str(list_path)]
    try:
        run_ffmpeg([*base, "-c", "copy", str(out)], log)
    except ExternalServiceError as exc:
        if exc.code == "ffmpeg_not_found":
            raise
        log.warning("highlights_concat_copy_failed", error=exc.message)
        run_ffmpeg([*base, *_ENCODE_ARGS, str(out)], log)
        return
    if not out.is_file() or out.stat().st_size == 0:
        log.warning("highlights_concat_copy_empty", out=str(out))
        run_ffmpeg([*base, *_ENCODE_ARGS, str(out)], log)
