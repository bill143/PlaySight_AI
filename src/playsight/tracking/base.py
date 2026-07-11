"""Tracker protocol (structural interface for all tracker engines)."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import numpy as np

from playsight.core.types import FrameDetection, TrackedBox


@runtime_checkable
class Tracker(Protocol):
    """Structural interface every tracker engine implements.

    Attributes:
        engine: Engine name reported in artifact metadata
            (``"bytetrack"`` / ``"simple"``).
    """

    engine: str

    def update(
        self, detections: list[FrameDetection], frame_bgr: np.ndarray | None = None
    ) -> list[TrackedBox]:
        """Advance the tracker by one frame.

        Args:
            detections: Detections for the current frame (all sharing the same
                ``frame_index`` / ``t_s``). May be empty; the call still ages
                internal track state.
            frame_bgr: The current frame (optional; unused by IOU-only engines).

        Returns:
            Tracked boxes for the current frame with stable ``track_id``s.
        """
        ...

    def reset(self) -> None:
        """Clear all internal track state (start of a new video)."""
        ...
