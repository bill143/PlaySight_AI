"""Competition module tables (CONTRACTS.md sections 5, 12, 18).

All tables are club-scoped (``club_id`` FK, indexed). ``CompetitionSource``
points at a registered adapter (see ``adapters.base``); ``last_sync_hash`` is
the change-detection hash of the most recent full adapter payload, and each
synced row carries its own ``content_hash`` for finer-grained diffing.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from playsight.core.ids import new_id
from playsight.db.base import Base
from playsight.db.models import utcnow


class FixtureStatus(StrEnum):
    """Lifecycle of a fixture as reported by the source."""

    SCHEDULED = "scheduled"
    LIVE = "live"
    FINISHED = "finished"
    POSTPONED = "postponed"
    CANCELLED = "cancelled"


class CompetitionSource(Base):
    """A configured competition data source (entry in the adapter registry)."""

    __tablename__ = "competition_sources"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    club_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("clubs.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    adapter_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    config_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    # Source attribution is REQUIRED (CONTRACTS.md section 18); copied from the
    # adapter at creation time so the UI can render it without the registry.
    attribution: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Change-detection hash (sha256 hex) of the last full adapter payload.
    last_sync_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )


class Fixture(Base):
    """A scheduled/played fixture, synced from a source or entered manually."""

    __tablename__ = "competition_fixtures"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    club_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("clubs.id"), nullable=False, index=True
    )
    source_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("competition_sources.id"), nullable=True, index=True
    )
    team_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("teams.id"), nullable=True)
    external_ref: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    competition_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    home_team: Mapped[str] = mapped_column(String(255), nullable=False)
    away_team: Mapped[str] = mapped_column(String(255), nullable=False)
    kickoff_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    venue: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # scheduled | live | finished | postponed | cancelled (FixtureStatus)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="scheduled")
    home_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    away_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Change-detection hash (sha256 hex) of this row's adapter record.
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )


class Standing(Base):
    """One league-table row, synced from a competition source."""

    __tablename__ = "competition_standings"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    club_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("clubs.id"), nullable=False, index=True
    )
    source_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("competition_sources.id"), nullable=True, index=True
    )
    competition_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    season: Mapped[str | None] = mapped_column(String(64), nullable=True)
    team_name: Mapped[str] = mapped_column(String(255), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    played: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    won: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    drawn: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    lost: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    goals_for: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    goals_against: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    points: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Change-detection hash (sha256 hex) of this row's adapter record.
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )
