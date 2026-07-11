"""Frame iteration utility for the vision pipeline."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import cv2
import numpy as np

from playsight.core.errors import ValidationFailed
from playsight.core.logging import get_logger

_DEFAULT_FPS = 30.0


def iter_frames(
    path: str | Path,
    stride: int = 1,
    max_frames: int | None = None,
) -> Iterator[tuple[int, float, np.ndarray]]:
    """Iterate frames of a video, yielding ``(frame_index, t_s, frame_bgr)``.

    Frames are read sequentially; every ``stride``-th frame is yielded (the
    frame index is the absolute index in the video, not the yielded count).
    ``t_s`` is ``frame_index / fps``.

    Args:
        path: Local filesystem path of the video.
        stride: Yield every Nth frame (must be >= 1).
        max_frames: Maximum number of frames to yield (None = no cap).

    Yields:
        Tuples of ``(frame_index, t_s, frame_bgr)`` where ``frame_bgr`` is a
        HxWx3 uint8 BGR numpy array.

    Raises:
        ValidationFailed: ``stride`` < 1 or the video cannot be opened.
    """
    if stride < 1:
        raise ValidationFailed(f"stride must be >= 1, got {stride}")
    p = Path(path)
    cap = cv2.VideoCapture(str(p))
    if not cap.isOpened():
        cap.release()
        raise ValidationFailed(f"could not open video for reading: {p}")

    fps = float(cap.get(cv2.CAP_PROP_FPS))
    if fps <= 0:
        log = get_logger(__name__)
        log.warning("fps_unavailable_using_default", path=str(p), fps=_DEFAULT_FPS)
        fps = _DEFAULT_FPS

    frame_index = 0
    yielded = 0
    try:
        while True:
            if max_frames is not None and yielded >= max_frames:
                break
            ok, frame = cap.read()
            if not ok or frame is None:
                break
            if frame_index % stride == 0:
                yield frame_index, frame_index / fps, frame
                yielded += 1
            frame_index += 1
    finally:
        cap.release()
