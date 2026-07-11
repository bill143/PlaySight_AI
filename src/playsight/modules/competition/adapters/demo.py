"""Deterministic demo competition adapter (static fixtures/standings, no network)."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from playsight.modules.competition.adapters.base import (
    FixtureRecord,
    StandingRecord,
    register_adapter,
)

_DEMO_LEAGUE = "PlaySight Demo League"


class DemoCompetitionAdapter:
    """Static, deterministic demo source (safe for tests/CI; hashes are stable)."""

    key = "demo"
    rate_limit_per_minute = 60
    attribution = "PlaySight demo data (synthetic). Not affiliated with any real competition."

    def fetch_fixtures(self, config: Mapping[str, Any]) -> list[FixtureRecord]:
        """Return a static, deterministic fixture list."""
        league = str(config.get("competition_name", _DEMO_LEAGUE))
        return [
            FixtureRecord(
                external_ref="demo-fx-001",
                home_team="PlaySight FC",
                away_team="Riverside Rovers",
                kickoff_at=datetime(2026, 8, 1, 14, 0, tzinfo=UTC),
                venue="PlaySight Arena",
                status="scheduled",
                competition_name=league,
            ),
            FixtureRecord(
                external_ref="demo-fx-002",
                home_team="Harbor United",
                away_team="PlaySight FC",
                kickoff_at=datetime(2026, 8, 8, 16, 30, tzinfo=UTC),
                venue="Harbor Park",
                status="scheduled",
                competition_name=league,
            ),
            FixtureRecord(
                external_ref="demo-fx-003",
                home_team="PlaySight FC",
                away_team="Northgate Athletic",
                kickoff_at=datetime(2026, 7, 25, 13, 0, tzinfo=UTC),
                venue="PlaySight Arena",
                status="finished",
                home_score=2,
                away_score=1,
                competition_name=league,
            ),
        ]

    def fetch_standings(self, config: Mapping[str, Any]) -> list[StandingRecord]:
        """Return a static, deterministic standings table."""
        league = str(config.get("competition_name", _DEMO_LEAGUE))
        season = str(config.get("season", "2026"))
        rows = [
            ("PlaySight FC", 1, 3, 2, 1, 0, 7, 3, 7),
            ("Harbor United", 2, 3, 2, 0, 1, 5, 4, 6),
            ("Riverside Rovers", 3, 3, 1, 1, 1, 4, 4, 4),
            ("Northgate Athletic", 4, 3, 0, 0, 3, 2, 7, 0),
        ]
        return [
            StandingRecord(
                team_name=name,
                position=position,
                played=played,
                won=won,
                drawn=drawn,
                lost=lost,
                goals_for=goals_for,
                goals_against=goals_against,
                points=points,
                competition_name=league,
                season=season,
            )
            for name, position, played, won, drawn, lost, goals_for, goals_against, points in rows
        ]


register_adapter(DemoCompetitionAdapter())
