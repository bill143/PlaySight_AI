"""Detector factory: pick YOLO when available, deterministic stub otherwise."""

from __future__ import annotations

import importlib.util

from playsight.config.settings import Settings
from playsight.core.logging import get_logger
from playsight.detection.base import PersonDetector
from playsight.detection.stub import StubDetector
from playsight.detection.yolo import YoloDetector

_DEFAULT_YOLO_MODEL = "yolov8n.pt"


def _cv_detection_available() -> bool:
    """Return whether the ultralytics package is importable (without importing it)."""
    try:
        return importlib.util.find_spec("ultralytics") is not None
    except (ImportError, ValueError):  # pragma: no cover - broken partial installs
        return False


def create_detector(settings: Settings) -> PersonDetector:
    """Create the best available person detector and log the engine choice.

    Uses :class:`YoloDetector` when the ``[cv]`` extra (ultralytics) is
    installed, otherwise falls back to the deterministic :class:`StubDetector`.

    Args:
        settings: Application settings (``pipeline.detection_conf`` is the
            confidence threshold; an optional ``pipeline.yolo_model`` overrides
            the default ``yolov8n.pt`` weights name).

    Returns:
        A ready-to-use detector implementing :class:`PersonDetector`.
    """
    log = get_logger(__name__)
    conf = settings.pipeline.detection_conf
    detector: PersonDetector
    if _cv_detection_available():
        model_name = str(getattr(settings.pipeline, "yolo_model", _DEFAULT_YOLO_MODEL))
        detector = YoloDetector(conf=conf, model_name=model_name)
        log.info("detector_selected", engine="yolo", model=model_name, conf=conf)
    else:
        detector = StubDetector(conf=conf)
        log.info(
            "detector_selected",
            engine="stub",
            conf=conf,
            reason="ultralytics not installed ([cv] extra)",
        )
    return detector
