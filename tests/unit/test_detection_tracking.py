"""Stub detector determinism and SimpleTracker id persistence / occlusion TTL."""

from __future__ import annotations

import numpy as np

from playsight.core.types import FrameDetection
from playsight.detection.stub import StubDetector
from playsight.tracking.simple import SimpleTracker, iou_xyxy


def _frame(height: int = 240, width: int = 320) -> np.ndarray:
    return np.zeros((height, width, 3), dtype=np.uint8)


def _detection(x1: float, frame_index: int = 0, t_s: float = 0.0) -> FrameDetection:
    return FrameDetection(
        frame_index=frame_index,
        t_s=t_s,
        x1=x1,
        y1=0.0,
        x2=x1 + 10.0,
        y2=20.0,
        confidence=0.9,
    )


class TestStubDetector:
    def test_engine_is_honest(self) -> None:
        assert StubDetector().engine == "stub"

    def test_deterministic_for_same_frame_index(self) -> None:
        detector = StubDetector(conf=0.35, num_boxes=5)
        first = detector.detect(_frame(), 10, 0.5)
        second = detector.detect(_frame(), 10, 0.5)
        assert first == second
        assert len(first) > 0

    def test_two_instances_agree(self) -> None:
        a = StubDetector(conf=0.35, num_boxes=6).detect(_frame(), 42, 1.4)
        b = StubDetector(conf=0.35, num_boxes=6).detect(_frame(), 42, 1.4)
        assert a == b

    def test_motion_over_frame_indices(self) -> None:
        detector = StubDetector(conf=0.35, num_boxes=4)
        assert detector.detect(_frame(), 0, 0.0) != detector.detect(_frame(), 30, 1.0)

    def test_boxes_within_frame_and_confidence_bounds(self) -> None:
        detector = StubDetector(conf=0.35, num_boxes=6)
        for frame_index in (0, 7, 99, 250):
            for det in detector.detect(_frame(), frame_index, frame_index / 30.0):
                assert 0.0 <= det.x1 < det.x2 <= 320.0
                assert 0.0 <= det.y1 < det.y2 <= 240.0
                assert 0.35 <= det.confidence <= 0.99
                assert det.frame_index == frame_index

    def test_confidence_threshold_filters(self) -> None:
        strict = StubDetector(conf=0.99, num_boxes=6)
        assert strict.detect(_frame(), 0, 0.0) == []


class TestSimpleTracker:
    def test_new_tracks_get_incrementing_ids(self) -> None:
        tracker = SimpleTracker()
        tracked = tracker.update([_detection(0.0), _detection(100.0)])
        assert [box.track_id for box in tracked] == [1, 2]

    def test_id_persists_across_small_motion(self) -> None:
        tracker = SimpleTracker(iou_threshold=0.3)
        first = tracker.update([_detection(0.0)])
        assert first[0].track_id == 1
        for step in range(1, 6):
            tracked = tracker.update([_detection(2.0 * step, frame_index=step)])
            assert tracked[0].track_id == 1

    def test_occlusion_within_ttl_keeps_id(self) -> None:
        tracker = SimpleTracker(iou_threshold=0.3, ttl=2)
        assert tracker.update([_detection(50.0)])[0].track_id == 1
        assert tracker.update([]) == []
        assert tracker.update([]) == []  # missed == ttl, still alive
        recovered = tracker.update([_detection(50.0, frame_index=3)])
        assert recovered[0].track_id == 1

    def test_occlusion_beyond_ttl_drops_track(self) -> None:
        tracker = SimpleTracker(iou_threshold=0.3, ttl=2)
        assert tracker.update([_detection(50.0)])[0].track_id == 1
        for _ in range(3):  # missed becomes 3 > ttl -> dropped
            tracker.update([])
        reborn = tracker.update([_detection(50.0, frame_index=4)])
        assert reborn[0].track_id == 2

    def test_low_iou_opens_new_track(self) -> None:
        tracker = SimpleTracker(iou_threshold=0.3)
        assert tracker.update([_detection(0.0)])[0].track_id == 1
        far = tracker.update([_detection(200.0, frame_index=1)])
        assert far[0].track_id == 2

    def test_two_tracks_keep_distinct_ids(self) -> None:
        tracker = SimpleTracker(iou_threshold=0.3)
        tracker.update([_detection(0.0), _detection(100.0)])
        tracked = tracker.update([_detection(2.0, frame_index=1), _detection(102.0, frame_index=1)])
        assert [box.track_id for box in tracked] == [1, 2]

    def test_reset_restarts_ids(self) -> None:
        tracker = SimpleTracker()
        tracker.update([_detection(0.0)])
        tracker.reset()
        assert tracker.update([_detection(0.0)])[0].track_id == 1

    def test_deterministic_association(self) -> None:
        def run() -> list[int]:
            tracker = SimpleTracker(iou_threshold=0.1)
            tracker.update([_detection(0.0), _detection(8.0), _detection(100.0)])
            tracked = tracker.update(
                [_detection(4.0, frame_index=1), _detection(101.0, frame_index=1)]
            )
            return [box.track_id for box in tracked]

        assert run() == run()


class TestIou:
    def test_identical_boxes(self) -> None:
        assert iou_xyxy((0, 0, 10, 10), (0, 0, 10, 10)) == 1.0

    def test_disjoint_boxes(self) -> None:
        assert iou_xyxy((0, 0, 10, 10), (20, 20, 30, 30)) == 0.0

    def test_half_overlap(self) -> None:
        value = iou_xyxy((0, 0, 10, 10), (5, 0, 15, 10))
        assert value == 50.0 / 150.0

    def test_degenerate_box_is_zero(self) -> None:
        assert iou_xyxy((0, 0, 0, 0), (0, 0, 10, 10)) == 0.0
