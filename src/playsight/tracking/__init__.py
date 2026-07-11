"""Multi-object tracking: ByteTrack via ``supervision`` with an IOU fallback.

Public interface (CONTRACTS.md section 7):

- ``Tracker`` protocol: ``update(detections, frame_bgr) -> list[TrackedBox]``
- ``ByteTrackTracker`` (lazy ``supervision`` import)
- ``SimpleTracker`` (deterministic greedy-IOU matcher with track TTL)
- ``create_tracker(settings) -> Tracker``
"""

from playsight.tracking.base import Tracker
from playsight.tracking.bytetrack import ByteTrackTracker
from playsight.tracking.factory import create_tracker
from playsight.tracking.simple import SimpleTracker, iou_matrix, iou_xyxy

__all__ = [
    "ByteTrackTracker",
    "SimpleTracker",
    "Tracker",
    "create_tracker",
    "iou_matrix",
    "iou_xyxy",
]
