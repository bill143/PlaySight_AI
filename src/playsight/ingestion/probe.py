"""Video probing: OpenCV first, ffprobe/ffmpeg fallback.

``probe_video`` returns a :class:`playsight.core.types.VideoInfo`. The primary
probe uses ``cv2.VideoCapture`` (opencv-python-headless is a core dependency).
When OpenCV cannot open the file or reports degenerate metadata, we fall back
to ``ffprobe`` (system binary) and finally to parsing ``ffmpeg -i`` stderr
(system ffmpeg or the binary bundled with ``imageio_ffmpeg``).
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import cv2

from playsight.core.errors import NotFoundError, ValidationFailed
from playsight.core.logging import get_logger
from playsight.core.types import VideoInfo

_FFPROBE_TIMEOUT_S = 60

_DURATION_RE = re.compile(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)")
_SIZE_RE = re.compile(r",\s*(\d{2,5})x(\d{2,5})[\s,]")
_FPS_RE = re.compile(r"(\d+(?:\.\d+)?)\s*fps")


def probe_video(path: str | Path) -> VideoInfo:
    """Probe a video file and return its metadata.

    Args:
        path: Local filesystem path to the video file.

    Returns:
        A :class:`VideoInfo` with duration, fps, dimensions, and frame count.

    Raises:
        NotFoundError: The file does not exist.
        ValidationFailed: The file exists but no probe strategy could read it.
    """
    log = get_logger(__name__)
    p = Path(path)
    if not p.is_file():
        raise NotFoundError(f"video file not found: {p}")

    info = _probe_cv2(p)
    engine = "cv2"
    if info is None:
        info = _probe_ffprobe(p)
        engine = "ffprobe"
    if info is None:
        info = _probe_ffmpeg_stderr(p)
        engine = "ffmpeg"
    if info is None:
        raise ValidationFailed(f"could not probe video (cv2/ffprobe/ffmpeg all failed): {p}")

    log.info(
        "video_probed",
        path=str(p),
        engine=engine,
        duration_s=info.duration_s,
        fps=info.fps,
        width=info.width,
        height=info.height,
        frame_count=info.frame_count,
    )
    return info


def _probe_cv2(path: Path) -> VideoInfo | None:
    """Probe with ``cv2.VideoCapture``; return None when unusable."""
    cap = cv2.VideoCapture(str(path))
    try:
        if not cap.isOpened():
            return None
        fps = float(cap.get(cv2.CAP_PROP_FPS))
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    finally:
        cap.release()
    if fps <= 0 or frame_count <= 0 or width <= 0 or height <= 0:
        return None
    return VideoInfo(
        duration_s=round(frame_count / fps, 4),
        fps=fps,
        width=width,
        height=height,
        frame_count=frame_count,
    )


def _probe_ffprobe(path: Path) -> VideoInfo | None:
    """Probe with the system ``ffprobe`` (JSON output); return None on failure."""
    ffprobe = shutil.which("ffprobe")
    if ffprobe is None:
        return None
    cmd = [
        ffprobe,
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height,r_frame_rate,nb_frames,duration",
        "-show_entries",
        "format=duration",
        "-of",
        "json",
        str(path),
    ]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=_FFPROBE_TIMEOUT_S, check=True
        )
        data = json.loads(proc.stdout)
        stream = data["streams"][0]
        num, _, den = str(stream.get("r_frame_rate", "0/1")).partition("/")
        fps = float(num) / float(den or 1.0)
        width = int(stream["width"])
        height = int(stream["height"])
        duration = _first_float(stream.get("duration"), data.get("format", {}).get("duration"))
        nb_frames = str(stream.get("nb_frames", ""))
        if nb_frames.isdigit():
            frame_count = int(nb_frames)
        elif duration is not None and fps > 0:
            frame_count = int(round(duration * fps))
        else:
            frame_count = 0
        if duration is None and fps > 0 and frame_count > 0:
            duration = frame_count / fps
    except Exception as exc:
        get_logger(__name__).warning("ffprobe_failed", path=str(path), error=str(exc))
        return None
    if not duration or fps <= 0 or width <= 0 or height <= 0 or frame_count <= 0:
        return None
    return VideoInfo(
        duration_s=round(float(duration), 4),
        fps=fps,
        width=width,
        height=height,
        frame_count=frame_count,
    )


def _probe_ffmpeg_stderr(path: Path) -> VideoInfo | None:
    """Last-resort probe: parse ``ffmpeg -i`` stderr; return None on failure."""
    exe = shutil.which("ffmpeg")
    if exe is None:
        try:
            import imageio_ffmpeg  # local import: binary resolution can be slow

            exe = imageio_ffmpeg.get_ffmpeg_exe()
        except Exception as exc:
            get_logger(__name__).warning("ffmpeg_binary_unavailable", error=str(exc))
            return None
    try:
        # `ffmpeg -i <file>` with no output exits non-zero by design; we only
        # want its stderr banner, so don't pass check=True.
        proc = subprocess.run(
            [exe, "-hide_banner", "-i", str(path)],
            capture_output=True,
            text=True,
            timeout=_FFPROBE_TIMEOUT_S,
        )
        stderr = proc.stderr or ""
        dur_m = _DURATION_RE.search(stderr)
        size_m = _SIZE_RE.search(stderr)
        fps_m = _FPS_RE.search(stderr)
        if not (dur_m and size_m and fps_m):
            return None
        hours, minutes, seconds = float(dur_m[1]), float(dur_m[2]), float(dur_m[3])
        duration = hours * 3600.0 + minutes * 60.0 + seconds
        width, height = int(size_m[1]), int(size_m[2])
        fps = float(fps_m[1])
    except Exception as exc:
        get_logger(__name__).warning("ffmpeg_probe_failed", path=str(path), error=str(exc))
        return None
    if duration <= 0 or fps <= 0 or width <= 0 or height <= 0:
        return None
    return VideoInfo(
        duration_s=round(duration, 4),
        fps=fps,
        width=width,
        height=height,
        frame_count=int(round(duration * fps)),
    )


def _first_float(*values: object) -> float | None:
    """Return the first value parseable as a positive float, else None."""
    for value in values:
        if value is None:
            continue
        try:
            parsed = float(str(value))
        except ValueError:
            continue
        if parsed > 0:
            return parsed
    return None
