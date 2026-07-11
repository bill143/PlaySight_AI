"""Small numeric/geometry helpers used by the detection module."""

from __future__ import annotations

from backend.detection.models import BoundingBox, Detection


def filter_by_confidence(detections: list[Detection], threshold: float) -> list[Detection]:
    """Return only detections with confidence >= threshold."""
    return [d for d in detections if d.confidence >= threshold]


def filter_by_class(detections: list[Detection], class_names: set[str]) -> list[Detection]:
    """Return only detections whose class_name is in `class_names`."""
    return [d for d in detections if d.class_name in class_names]


def non_max_suppression(detections: list[Detection], iou_threshold: float = 0.5) -> list[Detection]:
    """A simple greedy NMS implementation, used when the underlying detector does not do its own."""
    if not detections:
        return []

    sorted_dets = sorted(detections, key=lambda d: d.confidence, reverse=True)
    kept: list[Detection] = []

    for candidate in sorted_dets:
        if all(candidate.bbox.iou(existing.bbox) < iou_threshold for existing in kept):
            kept.append(candidate)

    return kept


def clip_bbox_to_frame(bbox: BoundingBox, frame_width: int, frame_height: int) -> BoundingBox:
    """Clamp a bounding box so it stays within the frame boundaries."""
    return BoundingBox(
        x1=max(0.0, min(bbox.x1, frame_width)),
        y1=max(0.0, min(bbox.y1, frame_height)),
        x2=max(0.0, min(bbox.x2, frame_width)),
        y2=max(0.0, min(bbox.y2, frame_height)),
    )
