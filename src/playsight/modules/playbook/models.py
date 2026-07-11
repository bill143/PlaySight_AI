"""Playbook module tables (CONTRACTS.md sections 5, 12).

Plays are immutable per version: editing creates a new row with
``version + 1`` and ``parent_play_id`` pointing at the previous version.
``PlayClipLink`` connects a play to a detected ``match_events`` row so coaches
can illustrate a play with real footage.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from playsight.core.ids import new_id
from playsight.db.base import Base
from playsight.db.models import utcnow


class PlayCategory(StrEnum):
    """Tactical category of a play."""

    SET_PIECE = "set_piece"
    DEFENSE = "defense"
    ATTACK = "attack"
    TRANSITION = "transition"


class Play(Base):
    """One version of a tactical play (new row per version)."""

    __tablename__ = "plays"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    club_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("clubs.id"), nullable=False, index=True
    )
    team_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("teams.id"), nullable=True)
    # set_piece | defense | attack | transition (PlayCategory)
    category: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    diagram_storage_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    # Previous version of this play (version history is a linked list of rows).
    parent_play_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("plays.id"), nullable=True, index=True
    )
    tags_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )


class PlayAssignment(Base):
    """A per-player (or per-role) responsibility within a play."""

    __tablename__ = "play_assignments"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    club_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("clubs.id"), nullable=False, index=True
    )
    play_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("plays.id"), nullable=False, index=True
    )
    player_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("players.id"), nullable=True
    )
    role: Mapped[str] = mapped_column(String(64), nullable=False)
    instructions: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )


class PlayClipLink(Base):
    """Links a play to a detected match event (video illustration)."""

    __tablename__ = "play_clip_links"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    club_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("clubs.id"), nullable=False, index=True
    )
    play_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("plays.id"), nullable=False, index=True
    )
    match_event_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("match_events.id"), nullable=False, index=True
    )
    note: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
