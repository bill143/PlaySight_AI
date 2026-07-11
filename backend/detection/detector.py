"""YOLO-based object detector with graceful degradation and a deterministic stub mode.

If the `ultralytics` package (and a valid model weights file) is unavailable,
the detector automatically falls back to a lightweight stub that returns
synthetic detections. This keeps the rest of the pipeline (tracking,
identification, analytics) fully testable without GPU/model dependencies.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np

from backend.core.config import settings
from backend.detection.models import BoundingBox, Detection
from backend.detection.utils import filter_by_confidence, non_max_suppression

logger = logging.getLogger(__name__)

try:  # pragma: no cover - exercised only when ultralytics is installed
    from ultralytics import YOLO  # type: ignore[import-not-found]

    _ULTRALYTICS_AVAILABLE = True
except ImportError:  # pragma: no cover - default path in CI/test envs
    YOLO = None  # type: ignore[assignment]
    _ULTRALYTICS_AVAILABLE = False

# COCO class ids relevant to sports analytics.
PERSON_CLASS_ID = 0
BALL_CLASS_ID = 32  # "sports ball" in the default COCO label set


class YOLODetector:
    """Wraps an Ultralytics YOLO model to detect players and the ball in a frame."""

    def __init__(
        self,
        model_path: str | None = None,
        confidence_threshold: float | None = None,
        force_stub: bool = False,
    ) -> None:
        self.model_path = model_path or settings.YOLO_MODEL_PATH
        self.confidence_threshold = (
            confidence_threshold if confidence_threshold is not None else settings.DETECTION_CONFIDENCE_THRESHOLD
        )
        self.use_stub = force_stub or not _ULTRALYTICS_AVAILABLE
        self._model: Any = None

        if not self.use_stub:
            try:
                self._model = YOLO(self.model_path)  # type: ignore[operator]
            except Exception as exc:  # pragma: no cover - defensive, depends on env
                logger.warning("Failed to load YOLO model '%s': %s. Falling back to stub mode.", self.model_path, exc)
                self.use_stub = True

    def detect(self, frame: np.ndarray) -> list[Detection]:
        """Run detection on a single BGR frame (as a numpy array) and return Detections."""
        if self.use_stub:
            return self._detect_stub(frame)
        return self._detect_real(frame)

    def _detect_real(self, frame: np.ndarray) -> list[Detection]:  # pragma: no cover - requires ultralytics+weights
        results = self._model.predict(frame, verbose=False)
        detections: list[Detection] = []

        for result in results:
            boxes = getattr(result, "boxes", None)
            if boxes is None:
                continue
            for box in boxes:
                xyxy = box.xyxy[0].tolist()
                conf = float(box.conf[0])
                cls_id = int(box.cls[0])
                class_name = result.names.get(cls_id, str(cls_id)) if hasattr(result, "names") else str(cls_id)
                detections.append(
                    Detection(
                        bbox=BoundingBox(*xyxy),
                        confidence=conf,
                        class_id=cls_id,
                        class_name=class_name,
                    )
                )

        detections = filter_by_confidence(detections, self.confidence_threshold)
        return non_max_suppression(detections)

    def _detect_stub(self, frame: np.ndarray) -> list[Detection]:
        """Deterministic synthetic detector used for tests/CI/local dev without a GPU.

        Produces a small, fixed set of plausible "player" bounding boxes sized
        relative to the input frame, plus one "ball" detection, so downstream
        tracking/identification code has realistic-looking inputs to operate on.
        """
        height, width = frame.shape[0], frame.shape[1]
        detections: list[Detection] = []

        box_w, box_h = width * 0.06, height * 0.18
        anchor_points = [
            (0.20, 0.50),
            (0.35, 0.40),
            (0.50, 0.55),
            (0.65, 0.45),
            (0.80, 0.50),
        ]

        for idx, (fx, fy) in enumerate(anchor_points):
            cx, cy = width * fx, height * fy
            detections.append(
                Detection(
                    bbox=BoundingBox(cx - box_w / 2, cy - box_h / 2, cx + box_w / 2, cy + box_h / 2),
                    confidence=0.9 - idx * 0.02,
                    class_id=PERSON_CLASS_ID,
                    class_name="person",
                )
            )

        ball_size = width * 0.015
        bx, by = width * 0.5, height * 0.6
        detections.append(
            Detection(
                bbox=BoundingBox(bx - ball_size / 2, by - ball_size / 2, bx + ball_size / 2, by + ball_size / 2),
                confidence=0.8,
                class_id=BALL_CLASS_ID,
                class_name="sports ball",
            )
        )

        return filter_by_confidence(detections, self.confidence_threshold)
