"""YOLO person detector (lazy ``ultralytics`` import — requires the ``[cv]`` extra)."""

from __future__ import annotations

from typing import Any

import numpy as np

from playsight.core.errors import ExternalServiceError
from playsight.core.logging import get_logger
from playsight.core.types import FrameDetection

#: COCO class id for "person".
_PERSON_CLASS_ID = 0


class YoloDetector:
    """Ultralytics YOLO person detector (``engine == "yolo"``).

    The model is loaded lazily on the first ``detect`` call so importing this
    module never pulls in torch/ultralytics. Only COCO class 0 (person) is kept.
    """

    engine = "yolo"

    def __init__(self, conf: float = 0.35, model_name: str = "yolov8n.pt") -> None:
        """Create a YOLO detector.

        Args:
            conf: Minimum detection confidence.
            model_name: Ultralytics model weights name or path (e.g. ``yolov8n.pt``).
        """
        self.conf = conf
        self.model_name = model_name
        self._model: Any = None

    def _ensure_model(self) -> Any:
        """Load the ultralytics model on first use.

        Raises:
            ExternalServiceError: ultralytics is not installed or weights failed to load.
        """
        if self._model is None:
            try:
                from ultralytics import YOLO  # heavy import: lazy by contract
            except ImportError as exc:  # pragma: no cover - requires missing extra
                raise ExternalServiceError(
                    "ultralytics is not installed; install the [cv] extra or use StubDetector",
                    code="cv_extra_missing",
                ) from exc
            try:
                self._model = YOLO(self.model_name)
            except Exception as exc:  # pragma: no cover - model download/load failure
                raise ExternalServiceError(
                    f"failed to load YOLO model {self.model_name!r}: {exc}",
                    code="yolo_model_load_failed",
                ) from exc
            get_logger(__name__).info("yolo_model_loaded", model=self.model_name, conf=self.conf)
        return self._model

    def detect(self, frame_bgr: np.ndarray, frame_index: int, t_s: float) -> list[FrameDetection]:
        """Detect persons in one BGR frame using YOLO.

        Args:
            frame_bgr: HxWx3 uint8 BGR image.
            frame_index: Absolute frame index in the source video.
            t_s: Timestamp of the frame in seconds.

        Returns:
            Person detections (COCO class 0 only) with confidence >= ``conf``.
        """
        model = self._ensure_model()
        results = model.predict(
            source=frame_bgr, conf=self.conf, classes=[_PERSON_CLASS_ID], verbose=False
        )
        detections: list[FrameDetection] = []
        if not results:
            return detections
        boxes = getattr(results[0], "boxes", None)
        if boxes is None or boxes.xyxy is None:
            return detections
        xyxy = boxes.xyxy.cpu().numpy()
        confs = boxes.conf.cpu().numpy() if boxes.conf is not None else np.ones(len(xyxy))
        for (x1, y1, x2, y2), confidence in zip(xyxy, confs, strict=False):
            detections.append(
                FrameDetection(
                    frame_index=frame_index,
                    t_s=t_s,
                    x1=float(x1),
                    y1=float(y1),
                    x2=float(x2),
                    y2=float(y2),
                    confidence=float(confidence),
                )
            )
        return detections
