"""Frame annotation: draws bounding boxes, track IDs, and jersey numbers onto video frames."""

from __future__ import annotations

import numpy as np

from backend.detection.models import BoundingBox
from backend.tracking.models import Track

_COLOR_PALETTE = [
    (11, 95, 255),
    (0, 200, 120),
    (255, 128, 0),
    (200, 0, 160),
    (255, 210, 0),
]


class FrameAnnotator:
    """Draws overlays (boxes, labels) onto a frame for annotated video export."""

    def _color_for_track(self, track_id: int) -> tuple[int, int, int]:
        return _COLOR_PALETTE[track_id % len(_COLOR_PALETTE)]

    def annotate_tracks(
        self,
        frame: np.ndarray,
        tracks: list[Track],
        jersey_numbers: dict[int, int | None] | None = None,
    ) -> np.ndarray:
        """Draw bounding boxes and labels for all tracks onto a copy of `frame`."""
        import cv2  # local import: keeps module importable even if opencv isn't fully functional headlessly

        annotated = frame.copy()
        jersey_numbers = jersey_numbers or {}

        for track in tracks:
            color = self._color_for_track(track.track_id)
            bbox = track.bbox
            pt1 = (int(bbox.x1), int(bbox.y1))
            pt2 = (int(bbox.x2), int(bbox.y2))
            cv2.rectangle(annotated, pt1, pt2, color, 2)

            number = jersey_numbers.get(track.track_id)
            label = f"#{number}" if number is not None else f"id:{track.track_id}"
            cv2.putText(
                annotated,
                label,
                (pt1[0], max(0, pt1[1] - 6)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                color,
                2,
                cv2.LINE_AA,
            )

        return annotated

    def draw_bbox(self, frame: np.ndarray, bbox: BoundingBox, label: str, color: tuple[int, int, int] = (11, 95, 255)) -> np.ndarray:
        """Draw a single labeled bounding box onto a copy of `frame`."""
        import cv2

        annotated = frame.copy()
        pt1, pt2 = (int(bbox.x1), int(bbox.y1)), (int(bbox.x2), int(bbox.y2))
        cv2.rectangle(annotated, pt1, pt2, color, 2)
        cv2.putText(annotated, label, (pt1[0], max(0, pt1[1] - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2, cv2.LINE_AA)
        return annotated
