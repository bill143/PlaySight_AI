"""Unit tests for the tracking package."""

from __future__ import annotations

from backend.detection.models import BoundingBox, Detection
from backend.tracking.bytetrack import ByteTrackStub
from backend.tracking.tracker import PlayerTracker, SimpleIoUTracker


def _det(x1: float, y1: float, x2: float, y2: float, confidence: float = 0.9) -> Detection:
    return Detection(bbox=BoundingBox(x1, y1, x2, y2), confidence=confidence, class_id=0, class_name="person")


class TestSimpleIoUTracker:
    def test_new_detection_creates_new_track(self) -> None:
        tracker = SimpleIoUTracker()
        tracks = tracker.update([_det(0, 0, 10, 10)])
        assert len(tracks) == 1
        assert tracks[0].track_id == 1

    def test_same_position_keeps_same_track_id(self) -> None:
        tracker = SimpleIoUTracker(iou_threshold=0.3)
        tracks1 = tracker.update([_det(0, 0, 10, 10)])
        tracks2 = tracker.update([_det(1, 1, 11, 11)])
        assert tracks1[0].track_id == tracks2[0].track_id

    def test_track_ages_out_after_max_age(self) -> None:
        tracker = SimpleIoUTracker(max_age=2)
        tracker.update([_det(0, 0, 10, 10)])
        tracker.update([])
        tracker.update([])
        tracks = tracker.update([])
        assert len(tracks) == 0


class TestByteTrackStub:
    def test_high_confidence_detection_creates_track(self) -> None:
        tracker = ByteTrackStub(high_conf_threshold=0.5)
        tracks = tracker.update([_det(0, 0, 10, 10, confidence=0.9)])
        assert len(tracks) == 1

    def test_low_confidence_detection_does_not_create_new_track(self) -> None:
        tracker = ByteTrackStub(high_conf_threshold=0.5, low_conf_threshold=0.1)
        tracks = tracker.update([_det(0, 0, 10, 10, confidence=0.2)])
        assert len(tracks) == 0

    def test_low_confidence_detection_matches_existing_track(self) -> None:
        tracker = ByteTrackStub(high_conf_threshold=0.5, low_conf_threshold=0.1)
        tracker.update([_det(0, 0, 10, 10, confidence=0.9)])
        tracks = tracker.update([_det(1, 1, 11, 11, confidence=0.2)])
        assert len(tracks) == 1

    def test_persistent_track_ids_across_frames(self) -> None:
        tracker = ByteTrackStub()
        ids_over_time = []
        for i in range(5):
            tracks = tracker.update([_det(i, i, i + 10, i + 10, confidence=0.9)])
            ids_over_time.append({t.track_id for t in tracks})

        # The same single object should keep a stable ID across all frames.
        assert all(ids == ids_over_time[0] for ids in ids_over_time)


class TestPlayerTracker:
    def test_update_returns_tracks(self) -> None:
        tracker = PlayerTracker(use_bytetrack=True)
        tracks = tracker.update([_det(0, 0, 10, 10)])
        assert len(tracks) == 1

    def test_reset_clears_tracks(self) -> None:
        tracker = PlayerTracker(use_bytetrack=False)
        tracker.update([_det(0, 0, 10, 10)])
        tracker.reset()
        tracks = tracker.update([_det(500, 500, 510, 510)])
        assert tracks[0].track_id == 1

    def test_falls_back_gracefully_on_internal_error(self, monkeypatch) -> None:
        tracker = PlayerTracker(use_bytetrack=True)

        def _raise(*args, **kwargs):
            raise RuntimeError("boom")

        monkeypatch.setattr(tracker._impl, "update", _raise)
        tracks = tracker.update([_det(0, 0, 10, 10)])
        assert isinstance(tracks, list)
