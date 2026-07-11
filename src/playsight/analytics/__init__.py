"""Analytics: rule-based event segmentation and per-player statistics.

Public interface (CONTRACTS.md section 7):

- :func:`compute_events` -- six-event heuristic segmentation (section 8).
- :func:`compute_player_stats` -- per-track stats rows with heatmaps.
"""

from playsight.analytics.events import compute_events
from playsight.analytics.stats import compute_player_stats

__all__ = ["compute_events", "compute_player_stats"]
