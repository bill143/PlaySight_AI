"""Competition service: club-scoped CRUD plus sync orchestration."""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from playsight.core.errors import NotFoundError
from playsight.modules.competition.adapters import available_adapters, get_adapter
from playsight.modules.competition.models import CompetitionSource, Fixture, Standing
from playsight.modules.competition.schemas import CompetitionSourceCreate, FixtureCreate
from playsight.modules.competition.sync import SyncResult, sync_competition


class CompetitionService:
    """CRUD and sync orchestration for competition sources, fixtures, standings.

    Every query is scoped to the caller's ``club_id``; cross-club access
    surfaces as ``NotFoundError`` (HTTP 404) per CONTRACTS.md section 6.
    """

    def __init__(self, db: Session) -> None:
        """Bind the service to an open database session."""
        self.db = db

    # -- sources ---------------------------------------------------------

    def create_source(self, club_id: str, payload: CompetitionSourceCreate) -> CompetitionSource:
        """Register a source; validates the adapter key and copies its attribution.

        Raises:
            ValidationFailed: If ``payload.adapter_key`` is not a registered adapter.
        """
        adapter = get_adapter(payload.adapter_key)
        source = CompetitionSource(
            club_id=club_id,
            name=payload.name,
            adapter_key=payload.adapter_key,
            config_json=dict(payload.config_json),
            attribution=adapter.attribution,
            enabled=payload.enabled,
        )
        self.db.add(source)
        self.db.commit()
        self.db.refresh(source)
        return source

    def list_sources(self, club_id: str) -> list[CompetitionSource]:
        """Return all competition sources configured for the club."""
        stmt = (
            select(CompetitionSource)
            .where(CompetitionSource.club_id == club_id)
            .order_by(CompetitionSource.created_at)
        )
        return list(self.db.scalars(stmt))

    def get_source(self, club_id: str, source_id: str) -> CompetitionSource:
        """Return one source, raising ``NotFoundError`` outside the club scope."""
        source = self.db.get(CompetitionSource, source_id)
        if source is None or source.club_id != club_id:
            raise NotFoundError(f"Competition source {source_id} not found.")
        return source

    def delete_source(self, club_id: str, source_id: str) -> None:
        """Delete a source together with its synced fixtures and standings."""
        source = self.get_source(club_id, source_id)
        self.db.execute(
            delete(Fixture).where(Fixture.club_id == club_id, Fixture.source_id == source.id)
        )
        self.db.execute(
            delete(Standing).where(Standing.club_id == club_id, Standing.source_id == source.id)
        )
        self.db.delete(source)
        self.db.commit()

    # -- fixtures / standings --------------------------------------------

    def create_fixture(self, club_id: str, payload: FixtureCreate) -> Fixture:
        """Create a manually entered fixture (no external source)."""
        fixture = Fixture(
            club_id=club_id,
            source_id=None,
            team_id=payload.team_id,
            external_ref=payload.external_ref,
            competition_name=payload.competition_name,
            home_team=payload.home_team,
            away_team=payload.away_team,
            kickoff_at=payload.kickoff_at,
            venue=payload.venue,
            status=payload.status.value,
            home_score=payload.home_score,
            away_score=payload.away_score,
        )
        self.db.add(fixture)
        self.db.commit()
        self.db.refresh(fixture)
        return fixture

    def list_fixtures(
        self, club_id: str, *, status: str | None = None, team_id: str | None = None
    ) -> list[Fixture]:
        """Return the club's fixtures, optionally filtered by status and team."""
        stmt = select(Fixture).where(Fixture.club_id == club_id)
        if status is not None:
            stmt = stmt.where(Fixture.status == status)
        if team_id is not None:
            stmt = stmt.where(Fixture.team_id == team_id)
        stmt = stmt.order_by(Fixture.kickoff_at)
        return list(self.db.scalars(stmt))

    def list_standings(
        self, club_id: str, *, competition_name: str | None = None
    ) -> list[Standing]:
        """Return the club's standings ordered by table position."""
        stmt = select(Standing).where(Standing.club_id == club_id)
        if competition_name is not None:
            stmt = stmt.where(Standing.competition_name == competition_name)
        stmt = stmt.order_by(Standing.competition_name, Standing.position)
        return list(self.db.scalars(stmt))

    # -- sync --------------------------------------------------------------

    def sync(self, club_id: str, *, source_id: str | None = None) -> list[SyncResult]:
        """Sync fixtures/standings for one source (or all enabled sources)."""
        return sync_competition(club_id, self.db, source_id=source_id)

    def list_adapters(self) -> list[dict]:
        """Describe the registered adapters (key, rate limit, attribution)."""
        return [
            {
                "key": adapter.key,
                "rate_limit_per_minute": adapter.rate_limit_per_minute,
                "attribution": adapter.attribution,
            }
            for adapter in available_adapters().values()
        ]

    def map_external_teams(self, club_id: str, source_id: str) -> dict[str, str]:
        """Map external team names from a source onto internal ``teams`` rows.

        # TODO(phase2): fuzzy-match adapter team names against ``teams.name``
        # (per club), persist confirmed mappings, and use them to attach
        # ``Fixture.team_id`` automatically during sync.
        """
        raise NotImplementedError(
            "TODO(phase2): external-team mapping is not implemented yet (see docs/ROADMAP.md)."
        )
