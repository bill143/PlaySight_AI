"""Tracking data models."""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.detection.models import BoundingBox


@dataclass
class Track:
    """A tracked entity persisted across frames."""

    track_id: int
    bbox: BoundingBox
    confidence: float
    class_name: str = "person"
    age: int = 0
    hits: int = 0
    time_since_update: int = 0
    history: list[BoundingBox] = field(default_factory=list)
