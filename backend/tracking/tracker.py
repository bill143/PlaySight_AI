"""Player tracking orchestration: PlayerTracker wraps ByteTrackStub with a simple IoU fallback."""

from __future__ import annotations

import logging

import numpy as np

from backend.core.config import settings
from backend.detection.models import Detection
from backend.tracking.bytetrack import ByteTrackStub
from backend.tracking.models import Track

logger = logging.getLogger(__name__)


class SimpleIoUTracker:
    """Minimal single-stage IoU tracker used as a fallback if ByteTrack fails."""

    def __init__(self, iou_threshold: float = 0.3, max_age: int = 30) -> None:
        self.iou_threshold = iou_threshold
        self.max_age = max_age
        self._tracks: dict[int, Track] = {}
        self._next_id = 1

    def update(self, detections: list[Detection]) -> list[Track]:
        unmatched_dets = list(detections)
        matched_ids: set[int] = set()

        for track in self._tracks.values():
            best_iou = 0.0
            best_det: Detection | None = None
            for det in unmatched_dets:
                iou = track.bbox.iou(det.bbox)
                if iou > best_iou and iou >= self.iou_threshold:
                    best_iou = iou
                    best_det = det

            if best_det is not None:
                track.bbox = best_det.bbox
                track.confidence = best_det.confidence
                track.hits += 1
                track.age += 1
                track.time_since_update = 0
                track.history.append(best_det.bbox)
                unmatched_dets.remove(best_det)
                matched_ids.add(track.track_id)
            else:
                track.time_since_update += 1
                track.age += 1

        for det in unmatched_dets:
            new_track = Track(
                track_id=self._next_id,
                bbox=det.bbox,
                confidence=det.confidence,
                class_name=det.class_name,
                age=1,
                hits=1,
                time_since_update=0,
                history=[det.bbox],
            )
            self._tracks[new_track.track_id] = new_track
            self._next_id += 1

        self._tracks = {tid: t for tid, t in self._tracks.items() if t.time_since_update <= self.max_age}
        return [t for t in self._tracks.values() if t.time_since_update == 0]


class PlayerTracker:
    """High-level tracker used by the pipeline to maintain persistent player track IDs."""

    def __init__(self, max_age: int | None = None, iou_threshold: float = 0.3, use_bytetrack: bool = True) -> None:
        self.max_age = max_age if max_age is not None else settings.TRACKER_MAX_AGE
        self.iou_threshold = iou_threshold
        self._impl: ByteTrackStub | SimpleIoUTracker

        if use_bytetrack:
            self._impl = ByteTrackStub(iou_threshold=iou_threshold, max_age=self.max_age)
        else:
            self._impl = SimpleIoUTracker(iou_threshold=iou_threshold, max_age=self.max_age)

    def update(self, detections: list[Detection], frame: np.ndarray | None = None) -> list[Track]:
        """Update tracker state with the current frame's detections.

        `frame` is accepted for API symmetry with detectors/future appearance-based
        re-identification but is unused by the current IoU-based implementation.
        """
        try:
            return self._impl.update(detections)
        except Exception as exc:  # pragma: no cover - defensive fallback
            logger.warning("Primary tracker failed (%s); falling back to SimpleIoUTracker.", exc)
            fallback = SimpleIoUTracker(iou_threshold=self.iou_threshold, max_age=self.max_age)
            self._impl = fallback
            return fallback.update(detections)

    def reset(self) -> None:
        """Reset tracker state, e.g. between separate video processing runs."""
        use_bytetrack = isinstance(self._impl, ByteTrackStub)
        if use_bytetrack:
            self._impl = ByteTrackStub(iou_threshold=self.iou_threshold, max_age=self.max_age)
        else:
            self._impl = SimpleIoUTracker(iou_threshold=self.iou_threshold, max_age=self.max_age)
