"""Match event detection and segmentation.

For the MVP, events are derived from simple heuristics over ball/player
proximity rather than a full action-recognition model. This keeps the
pipeline deterministic and testable while providing a clear extension point
(`EventDetector.detect`) for a future ML-based event classifier.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.detection.models import BoundingBox

BALL_CLASS_NAME = "sports ball"
POSSESSION_DISTANCE_PX = 60.0


@dataclass
class FrameObservation:
    """Per-frame positions needed for event detection."""

    frame_index: int
    timestamp_seconds: float
    ball_bbox: BoundingBox | None
    player_bboxes: dict[int, BoundingBox]  # track_id -> bbox


@dataclass
class MatchEventResult:
    event_type: str
    timestamp_seconds: float
    track_id: int | None
    confidence: float
    metadata: dict = field(default_factory=dict)


class EventDetector:
    """Detects possession changes, passes, and shot-like events from ball/player proximity."""

    def __init__(self, possession_distance_px: float = POSSESSION_DISTANCE_PX) -> None:
        self.possession_distance_px = possession_distance_px

    def _closest_player(self, ball_bbox: BoundingBox, player_bboxes: dict[int, BoundingBox]) -> tuple[int | None, float]:
        best_track: int | None = None
        best_dist = float("inf")
        bx, by = ball_bbox.center

        for track_id, bbox in player_bboxes.items():
            px, py = bbox.center
            dist = ((px - bx) ** 2 + (py - by) ** 2) ** 0.5
            if dist < best_dist:
                best_dist = dist
                best_track = track_id

        return best_track, best_dist

    def detect(self, frames: list[FrameObservation]) -> list[MatchEventResult]:
        """Detect possession/pass events across a sequence of frame observations."""
        events: list[MatchEventResult] = []
        current_possessor: int | None = None

        for frame in frames:
            if frame.ball_bbox is None or not frame.player_bboxes:
                continue

            closest_track, dist = self._closest_player(frame.ball_bbox, frame.player_bboxes)
            if closest_track is None or dist > self.possession_distance_px:
                continue

            if current_possessor is None:
                events.append(
                    MatchEventResult(
                        event_type="possession_start",
                        timestamp_seconds=frame.timestamp_seconds,
                        track_id=closest_track,
                        confidence=0.7,
                    )
                )
            elif closest_track != current_possessor:
                events.append(
                    MatchEventResult(
                        event_type="pass",
                        timestamp_seconds=frame.timestamp_seconds,
                        track_id=closest_track,
                        confidence=0.6,
                        metadata={"from_track_id": current_possessor, "to_track_id": closest_track},
                    )
                )

            current_possessor = closest_track

        return events

    def compute_possession_counts(self, events: list[MatchEventResult]) -> dict[int, int]:
        """Count how many times each track gained possession (start or via a pass)."""
        counts: dict[int, int] = {}
        for event in events:
            if event.event_type in ("possession_start", "pass") and event.track_id is not None:
                counts[event.track_id] = counts.get(event.track_id, 0) + 1
        return counts

    def compute_pass_counts(self, events: list[MatchEventResult]) -> dict[int, int]:
        """Count completed passes attributed to the track that made the pass."""
        counts: dict[int, int] = {}
        for event in events:
            if event.event_type == "pass":
                from_track = event.metadata.get("from_track_id")
                if from_track is not None:
                    counts[from_track] = counts.get(from_track, 0) + 1
        return counts
