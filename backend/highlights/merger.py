"""Merges multiple video clips into a single highlight reel."""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class ClipMerger:
    """Concatenates a list of video clips into one highlight video file."""

    def merge(self, clip_paths: list[str | Path], output_path: str | Path) -> Path:
        """Merge `clip_paths` in order into a single video at `output_path`."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        existing_clips = [Path(p) for p in clip_paths if Path(p).exists() and Path(p).stat().st_size > 0]

        if not existing_clips:
            logger.warning("No valid clips to merge; writing empty placeholder highlight file at %s", output_path)
            output_path.write_bytes(b"")
            return output_path

        try:
            from moviepy.editor import VideoFileClip, concatenate_videoclips  # type: ignore[import-not-found]

            subclips = [VideoFileClip(str(p)) for p in existing_clips]
            final = concatenate_videoclips(subclips, method="compose")
            final.write_videofile(str(output_path), codec="libx264", audio_codec="aac", logger=None)
            for sc in subclips:
                sc.close()
            final.close()
        except Exception as exc:  # pragma: no cover - depends on moviepy/ffmpeg availability
            logger.warning("Could not merge clips with moviepy (%s); concatenating raw bytes as fallback.", exc)
            with output_path.open("wb") as out_fh:
                for clip_path in existing_clips:
                    out_fh.write(clip_path.read_bytes())

        return output_path
