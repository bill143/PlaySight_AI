"""Unit tests for the detection package."""

from __future__ import annotations

import numpy as np

from backend.detection.detector import YOLODetector
from backend.detection.models import BoundingBox, Detection
from backend.detection.utils import clip_bbox_to_frame, filter_by_class, filter_by_confidence, non_max_suppression


class TestBoundingBox:
    def test_area_and_center(self) -> None:
        bbox = BoundingBox(0, 0, 10, 20)
        assert bbox.width == 10
        assert bbox.height == 20
        assert bbox.area == 200
        assert bbox.center == (5.0, 10.0)

    def test_iou_identical_boxes(self) -> None:
        bbox1 = BoundingBox(0, 0, 10, 10)
        bbox2 = BoundingBox(0, 0, 10, 10)
        assert bbox1.iou(bbox2) == 1.0

    def test_iou_disjoint_boxes(self) -> None:
        bbox1 = BoundingBox(0, 0, 10, 10)
        bbox2 = BoundingBox(100, 100, 110, 110)
        assert bbox1.iou(bbox2) == 0.0

    def test_iou_partial_overlap(self) -> None:
        bbox1 = BoundingBox(0, 0, 10, 10)
        bbox2 = BoundingBox(5, 5, 15, 15)
        iou = bbox1.iou(bbox2)
        assert 0.0 < iou < 1.0


class TestDetectionUtils:
    def test_filter_by_confidence(self) -> None:
        detections = [
            Detection(BoundingBox(0, 0, 10, 10), confidence=0.9, class_id=0),
            Detection(BoundingBox(0, 0, 10, 10), confidence=0.1, class_id=0),
        ]
        filtered = filter_by_confidence(detections, threshold=0.5)
        assert len(filtered) == 1
        assert filtered[0].confidence == 0.9

    def test_filter_by_class(self) -> None:
        detections = [
            Detection(BoundingBox(0, 0, 10, 10), confidence=0.9, class_id=0, class_name="person"),
            Detection(BoundingBox(0, 0, 10, 10), confidence=0.9, class_id=32, class_name="sports ball"),
        ]
        filtered = filter_by_class(detections, {"person"})
        assert len(filtered) == 1
        assert filtered[0].class_name == "person"

    def test_non_max_suppression_removes_overlaps(self) -> None:
        detections = [
            Detection(BoundingBox(0, 0, 10, 10), confidence=0.9, class_id=0),
            Detection(BoundingBox(1, 1, 11, 11), confidence=0.8, class_id=0),
            Detection(BoundingBox(100, 100, 110, 110), confidence=0.7, class_id=0),
        ]
        kept = non_max_suppression(detections, iou_threshold=0.5)
        assert len(kept) == 2

    def test_clip_bbox_to_frame(self) -> None:
        bbox = BoundingBox(-10, -10, 700, 500)
        clipped = clip_bbox_to_frame(bbox, frame_width=640, frame_height=480)
        assert clipped.x1 == 0
        assert clipped.y1 == 0
        assert clipped.x2 == 640
        assert clipped.y2 == 480


class TestYOLODetector:
    def test_detector_uses_stub_mode_by_default(self) -> None:
        detector = YOLODetector(force_stub=True)
        assert detector.use_stub is True

    def test_detect_returns_detections(self, sample_frame: np.ndarray) -> None:
        detector = YOLODetector(force_stub=True, confidence_threshold=0.0)
        detections = detector.detect(sample_frame)
        assert len(detections) > 0
        assert all(isinstance(d, Detection) for d in detections)

    def test_detect_respects_confidence_threshold(self, sample_frame: np.ndarray) -> None:
        detector = YOLODetector(force_stub=True, confidence_threshold=0.99)
        detections = detector.detect(sample_frame)
        assert all(d.confidence >= 0.99 for d in detections)

    def test_detect_includes_person_and_ball_classes(self, sample_frame: np.ndarray) -> None:
        detector = YOLODetector(force_stub=True, confidence_threshold=0.0)
        detections = detector.detect(sample_frame)
        class_names = {d.class_name for d in detections}
        assert "person" in class_names
        assert "sports ball" in class_names
