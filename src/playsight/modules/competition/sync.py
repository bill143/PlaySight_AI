"""Competition sync: adapter fetch, change detection (hash), and row refresh.

Change detection: the full adapter payload is hashed (sha256 of canonical
JSON). When it matches ``CompetitionSource.last_sync_hash`` the sync is a
no-op. Each synced row also stores a per-record ``content_hash`` so future
incremental diffing can skip unchanged rows.

# TODO(phase2): scheduled sync - register a Celery beat task in
# ``playsight.jobs`` that calls ``sync_competition`` per enabled source on an
# interval, honoring each adapter's ``rate_limit_per_minute``. Deliberately
# not wired into ``playsight/jobs/`` yet (see docs/ROADMAP.md).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from playsight.core.errors import NotFoundError
from playsight.core.logging import get_logger
from playsight.db.models import utcnow
from playsight.modules.competition.adapters import get_adapter
from playsight.modules.competition.models import CompetitionSource, Fixture, Standing

log = get_logger(__name__)


@dataclass(frozen=True)
class SyncResult:
    """Outcome of syncing one competition source."""

    source_id: str
    adapter_key: str
    changed: bool
    fixtures_upserted: int
    standings_upserted: int
    sync_hash: str
    attribution: str


def compute_change_hash(payload: object) -> str:
    """Return the sha256 hex digest of ``payload`` serialized as canonical JSON."""
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def sync_competition(
    club_id: str, db: Session, *, source_id: str | None = None
) -> list[SyncResult]:
    """Sync fixtures and standings for a club's enabled competition sources.

    Fetches from each source's adapter, hashes the payload, and skips sources
    whose data is unchanged since the last sync. Changed sources have their
    fixtures/standings replaced atomically within one transaction.

    Args:
        club_id: Tenant scope; only this club's sources are synced.
        db: Open SQLAlchemy session (committed per source).
        source_id: Optional single source to sync; all enabled sources when None.

    Returns:
        One ``SyncResult`` per enabled source that was processed.

    Raises:
        NotFoundError: If ``source_id`` is given but not found in this club.
        ValidationFailed: If a source references an unregistered adapter key.
    """
    stmt = select(CompetitionSource).where(CompetitionSource.club_id == club_id)
    if source_id is not None:
        stmt = stmt.where(CompetitionSource.id == source_id)
    sources = list(db.scalars(stmt))
    if source_id is not None and not sources:
        raise NotFoundError(f"Competition source {source_id} not found.")

    results: list[SyncResult] = []
    for source in sources:
        if not source.enabled:
            continue
        adapter = get_adapter(source.adapter_key)
        # TODO(phase2): throttle against adapter.rate_limit_per_minute before
        # fetching from real upstream sources (shared token-bucket per adapter).
        fixtures = adapter.fetch_fixtures(source.config_json)
        standings = adapter.fetch_standings(source.config_json)
        payload = {
            "fixtures": [asdict(record) for record in fixtures],
            "standings": [asdict(record) for record in standings],
        }
        sync_hash = compute_change_hash(payload)

        if sync_hash == source.last_sync_hash:
            source.last_synced_at = utcnow()
            db.commit()
            log.info("competition_sync_unchanged", source_id=source.id, adapter=adapter.key)
            results.append(
                SyncResult(
                    source_id=source.id,
                    adapter_key=adapter.key,
                    changed=False,
                    fixtures_upserted=0,
                    standings_upserted=0,
                    sync_hash=sync_hash,
                    attribution=adapter.attribution,
                )
            )
            continue

        db.execute(
            delete(Fixture).where(Fixture.club_id == club_id, Fixture.source_id == source.id)
        )
        db.execute(
            delete(Standing).where(Standing.club_id == club_id, Standing.source_id == source.id)
        )
        for fixture_record in fixtures:
            db.add(
                Fixture(
                    club_id=club_id,
                    source_id=source.id,
                    external_ref=fixture_record.external_ref,
                    competition_name=fixture_record.competition_name,
                    home_team=fixture_record.home_team,
                    away_team=fixture_record.away_team,
                    kickoff_at=fixture_record.kickoff_at,
                    venue=fixture_record.venue,
                    status=fixture_record.status,
                    home_score=fixture_record.home_score,
                    away_score=fixture_record.away_score,
                    content_hash=compute_change_hash(asdict(fixture_record)),
                )
            )
        for standing_record in standings:
            db.add(
                Standing(
                    club_id=club_id,
                    source_id=source.id,
                    competition_name=standing_record.competition_name,
                    season=standing_record.season,
                    team_name=standing_record.team_name,
                    position=standing_record.position,
                    played=standing_record.played,
                    won=standing_record.won,
                    drawn=standing_record.drawn,
                    lost=standing_record.lost,
                    goals_for=standing_record.goals_for,
                    goals_against=standing_record.goals_against,
                    points=standing_record.points,
                    content_hash=compute_change_hash(asdict(standing_record)),
                )
            )
        source.last_sync_hash = sync_hash
        source.last_synced_at = utcnow()
        db.commit()
        log.info(
            "competition_synced",
            source_id=source.id,
            adapter=adapter.key,
            fixtures=len(fixtures),
            standings=len(standings),
        )
        results.append(
            SyncResult(
                source_id=source.id,
                adapter_key=adapter.key,
                changed=True,
                fixtures_upserted=len(fixtures),
                standings_upserted=len(standings),
                sync_hash=sync_hash,
                attribution=adapter.attribution,
            )
        )
    return results
