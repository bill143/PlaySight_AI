"""Tracker factory: pick ByteTrack when available, greedy-IOU fallback otherwise."""

from __future__ import annotations

import importlib.util

from playsight.config.settings import Settings
from playsight.core.logging import get_logger
from playsight.tracking.base import Tracker
from playsight.tracking.bytetrack import ByteTrackTracker
from playsight.tracking.simple import SimpleTracker

_DEFAULT_IOU_THRESHOLD = 0.3
_DEFAULT_TTL = 30


def _cv_tracking_available() -> bool:
    """Return whether the supervision package is importable (without importing it)."""
    try:
        return importlib.util.find_spec("supervision") is not None
    except (ImportError, ValueError):  # pragma: no cover - broken partial installs
        return False


def create_tracker(settings: Settings) -> Tracker:
    """Create the best available tracker and log the engine choice.

    Uses :class:`ByteTrackTracker` when the ``[cv]`` extra (supervision) is
    installed, otherwise falls back to the deterministic :class:`SimpleTracker`.

    Args:
        settings: Application settings. Optional ``pipeline.track_iou_threshold``
            and ``pipeline.track_ttl`` tune the fallback tracker.

    Returns:
        A ready-to-use tracker implementing :class:`Tracker`.
    """
    log = get_logger(__name__)
    tracker: Tracker
    if _cv_tracking_available():
        tracker = ByteTrackTracker()
        log.info("tracker_selected", engine="bytetrack")
    else:
        iou_threshold = float(
            getattr(settings.pipeline, "track_iou_threshold", _DEFAULT_IOU_THRESHOLD)
        )
        ttl = int(getattr(settings.pipeline, "track_ttl", _DEFAULT_TTL))
        tracker = SimpleTracker(iou_threshold=iou_threshold, ttl=ttl)
        log.info(
            "tracker_selected",
            engine="simple",
            iou_threshold=iou_threshold,
            ttl=ttl,
            reason="supervision not installed ([cv] extra)",
        )
    return tracker
