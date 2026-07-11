"""Match event models (goals, shots, passes, etc.)."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Float, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base, JSONBType, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from backend.models.match import Match


class MatchEvent(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "match_events"

    match_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("matches.id", ondelete="CASCADE"))
    player_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("players.id", ondelete="SET NULL"), nullable=True
    )
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    timestamp_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    event_metadata: Mapped[dict] = mapped_column(JSONBType, nullable=False, default=dict)

    match: Mapped["Match"] = relationship("Match")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<MatchEvent {self.event_type}@{self.timestamp_seconds}s>"
