"""Player, PlayerTrack and PlayerIdentity models."""

from __future__ import annotations

import uuid

from sqlalchemy import Float, ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base, JSONBType, TimestampMixin, UUIDPrimaryKeyMixin


class Player(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "players"

    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    jersey_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    team_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("teams.id", ondelete="SET NULL"), nullable=True
    )
    position: Mapped[str | None] = mapped_column(String(100), nullable=True)

    identities: Mapped[list["PlayerIdentity"]] = relationship(
        "PlayerIdentity", back_populates="player", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Player {self.full_name} #{self.jersey_number}>"


class PlayerTrack(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A single tracked entity for a match, prior to identity resolution."""

    __tablename__ = "player_tracks"

    match_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("matches.id", ondelete="CASCADE"))
    track_id: Mapped[int] = mapped_column(Integer, nullable=False)
    detected_jersey_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    frame_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    avg_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    player_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("players.id", ondelete="SET NULL"), nullable=True
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<PlayerTrack track_id={self.track_id}>"


class PlayerIdentity(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Resolved mapping between a match track and a canonical Player identity."""

    __tablename__ = "player_identities"

    player_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("players.id", ondelete="CASCADE"))
    match_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("matches.id", ondelete="CASCADE"))
    track_id: Mapped[int] = mapped_column(Integer, nullable=False)
    resolution_method: Mapped[str] = mapped_column(String(50), nullable=False, default="ocr")
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    embedding_metadata: Mapped[dict] = mapped_column(JSONBType, nullable=False, default=dict)

    player: Mapped["Player"] = relationship("Player", back_populates="identities")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<PlayerIdentity player_id={self.player_id} track_id={self.track_id}>"
