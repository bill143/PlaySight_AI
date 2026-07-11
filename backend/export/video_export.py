"""Annotated video export (MP4)."""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)


class VideoExporter:
    """Writes a sequence of annotated frames out to an MP4 file using OpenCV's VideoWriter."""

    def __init__(self, fourcc: str = "mp4v") -> None:
        self.fourcc = fourcc

    def export(self, frames: list[np.ndarray], output_path: str | Path, fps: float = 25.0) -> Path:
        """Write `frames` (BGR numpy arrays, same size) to an MP4 file at `output_path`."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if not frames:
            logger.warning("No frames provided for video export; writing empty placeholder file at %s", output_path)
            output_path.write_bytes(b"")
            return output_path

        try:
            import cv2

            height, width = frames[0].shape[0], frames[0].shape[1]
            fourcc = cv2.VideoWriter_fourcc(*self.fourcc)
            writer = cv2.VideoWriter(str(output_path), fourcc, fps, (width, height))

            for frame in frames:
                writer.write(frame)

            writer.release()
        except Exception as exc:  # pragma: no cover - depends on opencv/codec availability
            logger.warning("Could not export real video with OpenCV (%s); writing placeholder file.", exc)
            output_path.write_bytes(b"")

        return output_path
