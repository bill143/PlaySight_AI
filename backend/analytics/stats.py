"""Per-player statistics computation from tracking data."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from backend.detection.models import BoundingBox


@dataclass
class TrackFrameSample:
    """A single frame's position sample for a track, used for movement stats."""

    frame_index: int
    timestamp_seconds: float
    bbox: BoundingBox


@dataclass
class PlayerStatsResult:
    player_key: str
    jersey_number: int | None
    distance_covered_m: float
    top_speed_kmh: float
    possessions: int
    passes: int
    shots: int
    goals: int
    time_on_ball_seconds: float
    heatmap_zones: dict[str, float] = field(default_factory=dict)


class PlayerStatsCalculator:
    """Computes movement and event-derived statistics for a single tracked player.

    `pixels_per_meter` converts pixel-space displacement into real-world
    distance; the default is a rough heuristic suitable for a standard
    broadcast-angle pitch shot and should be calibrated per venue for
    production accuracy.
    """

    def __init__(self, pixels_per_meter: float = 20.0) -> None:
        self.pixels_per_meter = pixels_per_meter

    def compute(
        self,
        player_key: str,
        jersey_number: int | None,
        samples: list[TrackFrameSample],
        possessions: int = 0,
        passes: int = 0,
        shots: int = 0,
        goals: int = 0,
        time_on_ball_seconds: float = 0.0,
    ) -> PlayerStatsResult:
        """Compute aggregate statistics from a chronologically-ordered list of samples."""
        distance_m = 0.0
        top_speed_kmh = 0.0
        zone_time: dict[str, float] = {}

        sorted_samples = sorted(samples, key=lambda s: s.frame_index)

        for prev, curr in zip(sorted_samples, sorted_samples[1:], strict=False):
            dx = curr.bbox.center[0] - prev.bbox.center[0]
            dy = curr.bbox.center[1] - prev.bbox.center[1]
            pixel_dist = math.hypot(dx, dy)
            meters = pixel_dist / self.pixels_per_meter
            distance_m += meters

            dt = curr.timestamp_seconds - prev.timestamp_seconds
            if dt > 0:
                speed_ms = meters / dt
                speed_kmh = speed_ms * 3.6
                top_speed_kmh = max(top_speed_kmh, speed_kmh)

            zone = self._zone_for_position(curr.bbox)
            zone_time[zone] = zone_time.get(zone, 0.0) + max(dt, 0.0)

        return PlayerStatsResult(
            player_key=player_key,
            jersey_number=jersey_number,
            distance_covered_m=round(distance_m, 2),
            top_speed_kmh=round(top_speed_kmh, 2),
            possessions=possessions,
            passes=passes,
            shots=shots,
            goals=goals,
            time_on_ball_seconds=round(time_on_ball_seconds, 2),
            heatmap_zones={k: round(v, 2) for k, v in zone_time.items()},
        )

    @staticmethod
    def _zone_for_position(bbox: BoundingBox, grid_cols: int = 3, grid_rows: int = 3) -> str:
        """Bucket a bbox center into a coarse zone label (e.g. 'zone_1_1') for heatmaps.

        Assumes normalized-ish frame coordinates aren't required: it uses the
        bbox center directly, relying on callers to pass frame-relative
        coordinates if finer granularity is desired.
        """
        col = min(grid_cols - 1, max(0, int(bbox.center[0] // 100) % grid_cols))
        row = min(grid_rows - 1, max(0, int(bbox.center[1] // 100) % grid_rows))
        return f"zone_{row}_{col}"
