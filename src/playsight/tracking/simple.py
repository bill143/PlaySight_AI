"""Deterministic greedy-IOU tracker (fallback when ``supervision`` is not installed).

Association strategy: compute the IOU matrix between the last known box of
each live track and the current detections, then greedily accept the highest
IOU pairs (ties broken by track id, then detection order). Unmatched
detections open new tracks with monotonically increasing ids; unmatched
tracks survive ``ttl`` further updates before being dropped.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from playsight.core.types import FrameDetection, TrackedBox


def iou_xyxy(box_a: Sequence[float], box_b: Sequence[float]) -> float:
    """Return the IOU of two boxes in ``(x1, y1, x2, y2)`` format.

    Args:
        box_a: First box.
        box_b: Second box.

    Returns:
        Intersection-over-union in ``[0, 1]`` (0.0 for degenerate boxes).
    """
    matrix = iou_matrix(
        np.asarray([box_a], dtype=np.float64), np.asarray([box_b], dtype=np.float64)
    )
    return float(matrix[0, 0])


def iou_matrix(boxes_a: np.ndarray, boxes_b: np.ndarray) -> np.ndarray:
    """Return the pairwise IOU matrix between two box arrays.

    Args:
        boxes_a: Array of shape ``(N, 4)`` in ``(x1, y1, x2, y2)`` format.
        boxes_b: Array of shape ``(M, 4)`` in ``(x1, y1, x2, y2)`` format.

    Returns:
        Array of shape ``(N, M)`` with IOU values in ``[0, 1]``.
    """
    a = np.asarray(boxes_a, dtype=np.float64).reshape(-1, 4)
    b = np.asarray(boxes_b, dtype=np.float64).reshape(-1, 4)
    if a.shape[0] == 0 or b.shape[0] == 0:
        return np.zeros((a.shape[0], b.shape[0]), dtype=np.float64)

    inter_x1 = np.maximum(a[:, None, 0], b[None, :, 0])
    inter_y1 = np.maximum(a[:, None, 1], b[None, :, 1])
    inter_x2 = np.minimum(a[:, None, 2], b[None, :, 2])
    inter_y2 = np.minimum(a[:, None, 3], b[None, :, 3])
    inter = np.clip(inter_x2 - inter_x1, 0.0, None) * np.clip(inter_y2 - inter_y1, 0.0, None)

    area_a = np.clip(a[:, 2] - a[:, 0], 0.0, None) * np.clip(a[:, 3] - a[:, 1], 0.0, None)
    area_b = np.clip(b[:, 2] - b[:, 0], 0.0, None) * np.clip(b[:, 3] - b[:, 1], 0.0, None)
    union = area_a[:, None] + area_b[None, :] - inter

    out = np.zeros_like(inter)
    np.divide(inter, union, out=out, where=union > 0)
    return out


@dataclass
class _TrackState:
    """Internal per-track state for :class:`SimpleTracker`."""

    track_id: int
    box: tuple[float, float, float, float]
    missed: int = 0


class SimpleTracker:
    """Deterministic greedy-IOU tracker (``engine == "simple"``)."""

    engine = "simple"

    def __init__(self, iou_threshold: float = 0.3, ttl: int = 30) -> None:
        """Create a simple IOU tracker.

        Args:
            iou_threshold: Minimum IOU for a detection to continue a track.
            ttl: Updates a track survives without a match before being dropped.
        """
        self.iou_threshold = iou_threshold
        self.ttl = max(0, ttl)
        self._tracks: dict[int, _TrackState] = {}
        self._next_id = 1

    def reset(self) -> None:
        """Clear all track state and restart track ids from 1."""
        self._tracks.clear()
        self._next_id = 1

    def update(
        self, detections: list[FrameDetection], frame_bgr: np.ndarray | None = None
    ) -> list[TrackedBox]:
        """Associate the current frame's detections with existing tracks.

        Args:
            detections: Detections for the current frame (may be empty).
            frame_bgr: Unused (accepted for interface compatibility).

        Returns:
            One :class:`TrackedBox` per input detection, in input order.
        """
        active_ids = sorted(self._tracks)
        assignment: dict[int, int] = {}  # detection index -> track id

        if detections and active_ids:
            track_boxes = np.asarray(
                [self._tracks[tid].box for tid in active_ids], dtype=np.float64
            )
            det_boxes = np.asarray([[d.x1, d.y1, d.x2, d.y2] for d in detections], dtype=np.float64)
            ious = iou_matrix(track_boxes, det_boxes)
            pairs = [
                (float(ious[ti, di]), active_ids[ti], di)
                for ti in range(len(active_ids))
                for di in range(len(detections))
                if ious[ti, di] >= self.iou_threshold
            ]
            # Highest IOU first; ties broken by track id then detection order
            # so results are fully deterministic.
            pairs.sort(key=lambda p: (-p[0], p[1], p[2]))
            used_tracks: set[int] = set()
            for _iou, pair_tid, pair_di in pairs:
                if pair_tid in used_tracks or pair_di in assignment:
                    continue
                assignment[pair_di] = pair_tid
                used_tracks.add(pair_tid)

        outputs: list[TrackedBox] = []
        touched: set[int] = set()
        for di, det in enumerate(detections):
            tid = assignment.get(di)
            if tid is None:
                tid = self._next_id
                self._next_id += 1
                self._tracks[tid] = _TrackState(track_id=tid, box=(det.x1, det.y1, det.x2, det.y2))
            else:
                state = self._tracks[tid]
                state.box = (det.x1, det.y1, det.x2, det.y2)
                state.missed = 0
            touched.add(tid)
            outputs.append(
                TrackedBox(
                    frame_index=det.frame_index,
                    t_s=det.t_s,
                    x1=det.x1,
                    y1=det.y1,
                    x2=det.x2,
                    y2=det.y2,
                    confidence=det.confidence,
                    track_id=tid,
                )
            )

        for tid in list(self._tracks):
            if tid in touched:
                continue
            state = self._tracks[tid]
            state.missed += 1
            if state.missed > self.ttl:
                del self._tracks[tid]

        return outputs
