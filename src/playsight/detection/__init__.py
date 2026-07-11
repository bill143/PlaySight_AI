"""Person detection: YOLO when the ``[cv]`` extra is installed, deterministic stub otherwise.

Public interface (CONTRACTS.md section 7):

- ``PersonDetector`` protocol: ``detect(frame_bgr, frame_index, t_s) -> list[FrameDetection]``
- ``YoloDetector`` (lazy ``ultralytics`` import, person class only)
- ``StubDetector`` (deterministic synthetic detections, ``engine == "stub"``)
- ``create_detector(settings) -> PersonDetector``
"""

from playsight.detection.base import PersonDetector
from playsight.detection.factory import create_detector
from playsight.detection.stub import StubDetector
from playsight.detection.yolo import YoloDetector

__all__ = ["PersonDetector", "StubDetector", "YoloDetector", "create_detector"]
