"""PersonDetector protocol (structural interface for all detector engines)."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import numpy as np

from playsight.core.types import FrameDetection


@runtime_checkable
class PersonDetector(Protocol):
    """Structural interface every detector engine implements.

    Attributes:
        conf: Minimum confidence threshold for emitted detections.
        engine: Engine name reported in artifact metadata (``"yolo"`` / ``"stub"``).
    """

    conf: float
    engine: str

    def detect(self, frame_bgr: np.ndarray, frame_index: int, t_s: float) -> list[FrameDetection]:
        """Detect persons in one BGR frame.

        Args:
            frame_bgr: HxWx3 uint8 BGR image.
            frame_index: Absolute frame index in the source video.
            t_s: Timestamp of the frame in seconds.

        Returns:
            Detections with absolute pixel coordinates and confidence >= ``conf``.
        """
        ...
