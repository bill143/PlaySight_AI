"""Movement heatmap generation (proxy implementation using position histograms)."""

from __future__ import annotations

import numpy as np

from backend.detection.models import BoundingBox


class HeatmapGenerator:
    """Builds a 2D occupancy heatmap for a track from its position history."""

    def __init__(self, grid_width: int = 20, grid_height: int = 12) -> None:
        self.grid_width = grid_width
        self.grid_height = grid_height

    def generate(self, positions: list[BoundingBox], frame_width: int, frame_height: int) -> np.ndarray:
        """Return a (grid_height, grid_width) array of normalized occupancy counts."""
        grid = np.zeros((self.grid_height, self.grid_width), dtype=np.float64)
        if not positions or frame_width <= 0 or frame_height <= 0:
            return grid

        for bbox in positions:
            cx, cy = bbox.center
            col = min(self.grid_width - 1, max(0, int((cx / frame_width) * self.grid_width)))
            row = min(self.grid_height - 1, max(0, int((cy / frame_height) * self.grid_height)))
            grid[row, col] += 1

        total = grid.sum()
        if total > 0:
            grid = grid / total
        return grid

    def to_zone_dict(self, grid: np.ndarray) -> dict[str, float]:
        """Flatten a heatmap grid into a `{'zone_row_col': value}` dict for JSON serialization."""
        zones: dict[str, float] = {}
        for row in range(grid.shape[0]):
            for col in range(grid.shape[1]):
                value = float(grid[row, col])
                if value > 0:
                    zones[f"zone_{row}_{col}"] = round(value, 4)
        return zones
