"""Deterministic stub person detector (no CV extra required).

Produces ``num_boxes`` synthetic "players" moving along smooth sinusoid paths.
Every output is a pure function of ``frame_index`` (and the frame size), so the
stub is fully deterministic and box motion is continuous enough for IOU-based
tracking to associate boxes across strided frames.
"""

from __future__ import annotations

import math

import numpy as np

from playsight.core.types import FrameDetection

#: Frames per full sinusoid cycle: slow, smooth motion that survives frame striding.
_PERIOD_FRAMES = 300.0


class StubDetector:
    """Deterministic synthetic person detector (``engine == "stub"``)."""

    engine = "stub"

    def __init__(self, conf: float = 0.35, num_boxes: int = 6) -> None:
        """Create a stub detector.

        Args:
            conf: Minimum confidence for emitted detections.
            num_boxes: Number of synthetic moving boxes per frame.
        """
        self.conf = conf
        self.num_boxes = max(1, num_boxes)

    def detect(self, frame_bgr: np.ndarray, frame_index: int, t_s: float) -> list[FrameDetection]:
        """Return deterministic synthetic detections for one frame.

        Args:
            frame_bgr: HxWx3 uint8 BGR image (only its size is used).
            frame_index: Absolute frame index (seeds the sinusoid phase).
            t_s: Timestamp in seconds (copied onto detections).

        Returns:
            Synthetic detections with confidence >= ``conf``.
        """
        height, width = int(frame_bgr.shape[0]), int(frame_bgr.shape[1])
        box_w = max(4.0, 0.06 * width)
        box_h = max(8.0, 0.16 * height)
        angle = 2.0 * math.pi * frame_index / _PERIOD_FRAMES

        detections: list[FrameDetection] = []
        for i in range(self.num_boxes):
            phase = 2.0 * math.pi * i / self.num_boxes
            cx = width * (0.5 + 0.35 * math.sin(angle + phase))
            cy = height * (0.5 + 0.30 * math.cos(0.7 * angle + 1.7 * phase))
            x1 = min(max(cx - box_w / 2.0, 0.0), width - 1.0)
            y1 = min(max(cy - box_h / 2.0, 0.0), height - 1.0)
            x2 = min(max(cx + box_w / 2.0, x1 + 1.0), float(width))
            y2 = min(max(cy + box_h / 2.0, y1 + 1.0), float(height))
            confidence = 0.88 - 0.03 * i + 0.05 * math.sin(angle * 2.0 + phase)
            confidence = max(0.05, min(0.99, confidence))
            if confidence < self.conf:
                continue
            detections.append(
                FrameDetection(
                    frame_index=frame_index,
                    t_s=t_s,
                    x1=round(x1, 2),
                    y1=round(y1, 2),
                    x2=round(x2, 2),
                    y2=round(y2, 2),
                    confidence=round(confidence, 4),
                )
            )
        return detections
