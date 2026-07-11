"""Detection and tracking evaluation metrics (precision/recall, IoU-based matching, MOTA-lite)."""

from __future__ import annotations

from dataclasses import dataclass

from backend.detection.models import BoundingBox, Detection
from backend.tracking.models import Track


@dataclass
class DetectionMetrics:
    true_positives: int
    false_positives: int
    false_negatives: int

    @property
    def precision(self) -> float:
        denom = self.true_positives + self.false_positives
        return self.true_positives / denom if denom else 0.0

    @property
    def recall(self) -> float:
        denom = self.true_positives + self.false_negatives
        return self.true_positives / denom if denom else 0.0

    @property
    def f1_score(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if (p + r) else 0.0


def evaluate_detections(
    predicted: list[Detection], ground_truth: list[BoundingBox], iou_threshold: float = 0.5
) -> DetectionMetrics:
    """Compute precision/recall/F1 for one frame's detections against ground truth boxes."""
    matched_gt: set[int] = set()
    true_positives = 0

    for pred in predicted:
        best_iou = 0.0
        best_idx = -1
        for idx, gt_box in enumerate(ground_truth):
            if idx in matched_gt:
                continue
            iou = pred.bbox.iou(gt_box)
            if iou > best_iou:
                best_iou = iou
                best_idx = idx

        if best_iou >= iou_threshold and best_idx >= 0:
            matched_gt.add(best_idx)
            true_positives += 1

    false_positives = len(predicted) - true_positives
    false_negatives = len(ground_truth) - true_positives

    return DetectionMetrics(
        true_positives=true_positives,
        false_positives=max(0, false_positives),
        false_negatives=max(0, false_negatives),
    )


@dataclass
class TrackingMetrics:
    """Simplified tracking quality metrics (a lightweight MOTA-style proxy)."""

    id_switches: int
    fragmentations: int
    total_frames: int

    @property
    def stability_score(self) -> float:
        """A [0, 1] score penalized by ID switches and track fragmentations."""
        if self.total_frames == 0:
            return 1.0
        penalty = (self.id_switches + self.fragmentations) / self.total_frames
        return max(0.0, 1.0 - penalty)


def evaluate_tracking(track_history: list[list[Track]]) -> TrackingMetrics:
    """Estimate ID switches and fragmentations from consecutive-frame track ID sets."""
    id_switches = 0
    fragmentations = 0
    previous_ids: set[int] = set()

    for frame_tracks in track_history:
        current_ids = {t.track_id for t in frame_tracks}
        if previous_ids and not current_ids.issubset(previous_ids) and not previous_ids.issubset(current_ids):
            disappeared = previous_ids - current_ids
            appeared = current_ids - previous_ids
            if disappeared and appeared:
                id_switches += min(len(disappeared), len(appeared))
        if previous_ids and not current_ids:
            fragmentations += 1
        previous_ids = current_ids

    return TrackingMetrics(id_switches=id_switches, fragmentations=fragmentations, total_frames=len(track_history))
