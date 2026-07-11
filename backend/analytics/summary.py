"""Match summary generation aggregating stats, events, and metadata into one JSON document."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

from backend.analytics.events import MatchEventResult
from backend.analytics.stats import PlayerStatsResult


@dataclass
class MatchSummary:
    match_id: str
    generated_at: str
    total_players_tracked: int
    total_events: int
    duration_seconds: float
    player_stats: list[dict[str, Any]] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class MatchSummaryBuilder:
    """Builds a `MatchSummary` document from computed player stats and detected events."""

    def build(
        self,
        match_id: str,
        duration_seconds: float,
        player_stats: list[PlayerStatsResult],
        events: list[MatchEventResult],
        extra: dict[str, Any] | None = None,
    ) -> MatchSummary:
        return MatchSummary(
            match_id=match_id,
            generated_at=datetime.now(UTC).isoformat(),
            total_players_tracked=len(player_stats),
            total_events=len(events),
            duration_seconds=round(duration_seconds, 2),
            player_stats=[asdict(s) for s in player_stats],
            events=[asdict(e) for e in events],
            extra=extra or {},
        )
