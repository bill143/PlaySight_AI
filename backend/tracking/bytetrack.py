"""Simplified ByteTrack implementation stub.

This provides the core two-stage (high-confidence / low-confidence)
association logic that ByteTrack is known for, using IoU as the association
metric instead of a full Kalman filter. It is intentionally lightweight so it
has no heavyweight dependencies (e.g. `lap`, `cython_bbox`) and remains fully
unit-testable. A production deployment could swap this out for the official
ByteTrack/DeepSORT implementation without changing the `PlayerTracker` API.
"""

from __future__ import annotations

from backend.detection.models import Detection
from backend.tracking.models import Track


class ByteTrackStub:
    """Two-stage IoU-based association tracker inspired by ByteTrack."""

    def __init__(
        self,
        high_conf_threshold: float = 0.5,
        low_conf_threshold: float = 0.1,
        iou_threshold: float = 0.3,
        max_age: int = 30,
    ) -> None:
        self.high_conf_threshold = high_conf_threshold
        self.low_conf_threshold = low_conf_threshold
        self.iou_threshold = iou_threshold
        self.max_age = max_age

        self._tracks: dict[int, Track] = {}
        self._next_id = 1

    @property
    def active_tracks(self) -> list[Track]:
        return [t for t in self._tracks.values() if t.time_since_update == 0]

    def _match(self, detections: list[Detection], candidate_tracks: list[Track]) -> tuple[
        dict[int, Detection], list[Detection]
    ]:
        """Greedy IoU matching between candidate tracks and detections.

        Returns a mapping of track_id -> matched Detection, and the list of
        detections that were not matched to any track.
        """
        matched: dict[int, Detection] = {}
        unmatched = list(detections)

        # Sort by best possible IoU to encourage a stable greedy assignment.
        pairs: list[tuple[float, Track, Detection]] = []
        for track in candidate_tracks:
            for det in detections:
                iou = track.bbox.iou(det.bbox)
                if iou >= self.iou_threshold:
                    pairs.append((iou, track, det))
        pairs.sort(key=lambda p: p[0], reverse=True)

        used_tracks: set[int] = set()
        used_dets: set[int] = set()
        for _iou, track, det in pairs:
            if track.track_id in used_tracks or id(det) in used_dets:
                continue
            matched[track.track_id] = det
            used_tracks.add(track.track_id)
            used_dets.add(id(det))

        unmatched = [d for d in unmatched if id(d) not in used_dets]
        return matched, unmatched

    def update(self, detections: list[Detection]) -> list[Track]:
        """Advance the tracker one frame given the current frame's detections."""
        high_conf = [d for d in detections if d.confidence >= self.high_conf_threshold]
        low_conf = [d for d in detections if self.low_conf_threshold <= d.confidence < self.high_conf_threshold]

        existing_tracks = list(self._tracks.values())

        # Stage 1: match high-confidence detections against all existing tracks.
        matched_high, unmatched_high = self._match(high_conf, existing_tracks)
        matched_ids = set(matched_high.keys())
        remaining_tracks = [t for t in existing_tracks if t.track_id not in matched_ids]

        # Stage 2: match low-confidence detections against tracks still unmatched.
        matched_low, _unmatched_low = self._match(low_conf, remaining_tracks)

        for track_id, det in {**matched_high, **matched_low}.items():
            track = self._tracks[track_id]
            track.bbox = det.bbox
            track.confidence = det.confidence
            track.class_name = det.class_name
            track.hits += 1
            track.age += 1
            track.time_since_update = 0
            track.history.append(det.bbox)

        matched_this_frame = set(matched_high.keys()) | set(matched_low.keys())

        # Age out tracks that received no update this frame.
        for track in existing_tracks:
            if track.track_id not in matched_this_frame:
                track.time_since_update += 1
                track.age += 1

        # Start new tracks for unmatched high-confidence detections.
        for det in unmatched_high:
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

        # Drop stale tracks.
        self._tracks = {
            tid: t for tid, t in self._tracks.items() if t.time_since_update <= self.max_age
        }

        return self.active_tracks
