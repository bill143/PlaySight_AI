"""ByteTrack tracker via ``supervision`` (lazy import — requires the ``[cv]`` extra)."""

from __future__ import annotations

from typing import Any

import numpy as np

from playsight.core.errors import ExternalServiceError
from playsight.core.types import FrameDetection, TrackedBox

#: Class id assigned to all detections handed to ByteTrack (person only).
_PERSON_CLASS_ID = 0


class ByteTrackTracker:
    """ByteTrack multi-object tracker wrapping ``supervision.ByteTrack``.

    ``engine == "bytetrack"``. The ``supervision`` package is imported lazily
    in ``__init__`` so importing this module never requires the ``[cv]`` extra.
    """

    engine = "bytetrack"

    def __init__(self) -> None:
        """Create the underlying ``supervision.ByteTrack`` instance.

        Raises:
            ExternalServiceError: ``supervision`` is not installed.
        """
        try:
            import supervision as sv  # heavy import: lazy by contract
        except ImportError as exc:  # pragma: no cover - requires missing extra
            raise ExternalServiceError(
                "supervision is not installed; install the [cv] extra or use SimpleTracker",
                code="cv_extra_missing",
            ) from exc
        self._sv: Any = sv
        self._tracker: Any = sv.ByteTrack()

    def reset(self) -> None:
        """Clear all track state (start of a new video)."""
        self._tracker.reset()

    def update(
        self, detections: list[FrameDetection], frame_bgr: np.ndarray | None = None
    ) -> list[TrackedBox]:
        """Advance ByteTrack by one frame and return tracked boxes.

        Args:
            detections: Detections for the current frame (all sharing the same
                ``frame_index`` / ``t_s``). May be empty; the call still ages
                lost tracks.
            frame_bgr: Unused (accepted for interface compatibility).

        Returns:
            Tracked boxes for detections ByteTrack kept and associated.
        """
        sv = self._sv
        if detections:
            sv_detections = sv.Detections(
                xyxy=np.asarray([[d.x1, d.y1, d.x2, d.y2] for d in detections], dtype=np.float32),
                confidence=np.asarray([d.confidence for d in detections], dtype=np.float32),
                class_id=np.full(len(detections), _PERSON_CLASS_ID, dtype=int),
            )
            frame_index = detections[0].frame_index
            t_s = detections[0].t_s
        else:
            sv_detections = sv.Detections.empty()
            frame_index = -1
            t_s = 0.0

        tracked = self._tracker.update_with_detections(sv_detections)

        outputs: list[TrackedBox] = []
        tracker_ids = tracked.tracker_id
        if tracker_ids is None:
            return outputs
        confidences = tracked.confidence
        for i in range(len(tracked)):
            if tracker_ids[i] is None:
                continue
            x1, y1, x2, y2 = (float(v) for v in tracked.xyxy[i])
            confidence = float(confidences[i]) if confidences is not None else 0.0
            outputs.append(
                TrackedBox(
                    frame_index=frame_index,
                    t_s=t_s,
                    x1=x1,
                    y1=y1,
                    x2=x2,
                    y2=y2,
                    confidence=confidence,
                    track_id=int(tracker_ids[i]),
                )
            )
        return outputs
