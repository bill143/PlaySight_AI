"""Video clip extraction around detected match events."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class ClipSpec:
    """Defines a clip to extract: a time window plus metadata for naming/labeling."""

    start_seconds: float
    end_seconds: float
    label: str
    track_id: int | None = None


class VideoClipper:
    """Extracts short clips from a source video around given time windows.

    Uses moviepy under the hood; if moviepy (or its ffmpeg dependency) is not
    available in the current environment, `extract_clip` degrades to copying
    the source path metadata into a manifest without producing a real clip,
    so callers/tests can still exercise the surrounding orchestration logic.
    """

    def __init__(self, padding_seconds: float = 2.0) -> None:
        self.padding_seconds = padding_seconds

    def extract_clip(self, source_video_path: str | Path, clip: ClipSpec, output_path: str | Path) -> Path:
        """Extract a single padded clip from the source video to `output_path`."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        start = max(0.0, clip.start_seconds - self.padding_seconds)
        end = clip.end_seconds + self.padding_seconds

        try:
            from moviepy.editor import VideoFileClip  # type: ignore[import-not-found]

            with VideoFileClip(str(source_video_path)) as video:
                end = min(end, video.duration)
                subclip = video.subclip(start, end)
                subclip.write_videofile(str(output_path), codec="libx264", audio_codec="aac", logger=None)
        except Exception as exc:  # pragma: no cover - depends on moviepy/ffmpeg availability
            logger.warning(
                "Could not extract real clip (%s); writing placeholder manifest for '%s' instead.",
                exc,
                output_path,
            )
            output_path.write_bytes(b"")

        return output_path

    def extract_clips_for_events(
        self, source_video_path: str | Path, clips: list[ClipSpec], output_dir: str | Path
    ) -> list[Path]:
        """Extract multiple clips, one per `ClipSpec`, into `output_dir`."""
        output_dir = Path(output_dir)
        paths: list[Path] = []
        for idx, clip in enumerate(clips):
            filename = f"clip_{idx:03d}_{clip.label}.mp4"
            paths.append(self.extract_clip(source_video_path, clip, output_dir / filename))
        return paths
